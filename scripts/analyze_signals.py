"""
analyze_signals.py — 채팅·음량·자막에서 하이라이트 후보 신호 추출

사용법:
    python scripts/analyze_signals.py 260504

입력:
    <YYMMDD>/vod.mp4
    <YYMMDD>/chat.json        (없으면 생략)
    <YYMMDD>/transcript.json  (없으면 생략)

출력:
    <YYMMDD>/signals.json
        {
          "version": 1,
          "duration": 14820.5,
          "candidates": [
            {"start": 1830, "end": 1885, "score": 87,
             "reasons": ["chat_burst", "volume_peak", "laughter"]},
            ...
          ]
        }

이 스크립트는 단순 통계만 합니다. "왜 재밌는지" 판단은 다음 단계의 AI 스크리닝이 합니다.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

import numpy as np

WINDOW_SEC = 10        # 10초 윈도우로 카운트
PEAK_RATIO = 2.5       # 평균 대비 N배 이상이면 피크
MIN_CLIP = 25          # 후보 최소 길이(초)
MAX_CLIP = 90          # 후보 최대 길이(초)
PAD_BEFORE = 8
PAD_AFTER = 5

LAUGH_PAT = re.compile(r"ㅋ{2,}|ㅎ{2,}|ㅋㅋ|kekw|lul|lmao", re.IGNORECASE)
EMOTE_PAT = re.compile(r"[\U0001F600-\U0001F64F\U0001F900-\U0001F9FF]")


def folder(yymmdd: str) -> Path:
    p = Path(yymmdd)
    if not p.exists():
        sys.exit(f"[X] 폴더 없음: {p.resolve()}")
    return p


def get_duration_seconds(vod: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(vod)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        sys.exit("[X] ffprobe 실패. ffmpeg 설치를 확인하세요.")
    return float(res.stdout.strip())


def extract_loudness(vod: Path, duration: float) -> np.ndarray:
    """ffmpeg로 1초 단위 RMS 음량 배열 추출."""
    print(f"[.] 음량 분석 중...")
    sr = 8000  # 다운샘플
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "audio.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(vod),
             "-ac", "1", "-ar", str(sr),
             "-vn", str(wav)],
            capture_output=True, check=True,
        )
        import soundfile as sf
        data, _ = sf.read(str(wav))

    samples_per_sec = sr
    n_secs = int(len(data) / samples_per_sec)
    rms = np.zeros(n_secs)
    for i in range(n_secs):
        chunk = data[i * samples_per_sec:(i + 1) * samples_per_sec]
        if len(chunk) > 0:
            rms[i] = float(np.sqrt(np.mean(chunk ** 2)))
    return rms


def chat_signals(chat_path: Path, duration: float) -> tuple[np.ndarray, np.ndarray]:
    """초 단위 채팅 메시지 수, 웃음 강도 배열."""
    n = int(duration) + 1
    counts = np.zeros(n)
    laughs = np.zeros(n)
    if not chat_path.exists():
        return counts, laughs

    data = json.loads(chat_path.read_text(encoding="utf-8"))
    for c in data.get("chats", []):
        t_ms = c.get("time_ms")
        if t_ms is None:
            continue
        sec = int(t_ms / 1000)
        if 0 <= sec < n:
            counts[sec] += 1
            msg = c.get("msg") or ""
            laugh_score = len(LAUGH_PAT.findall(msg))
            emote_score = len(EMOTE_PAT.findall(msg))
            laughs[sec] += laugh_score + emote_score
    return counts, laughs


def transcript_density(transcript_path: Path, duration: float) -> np.ndarray:
    """초 단위 발화 단어 수 (스트리머가 빠르게 말하는 구간 = 흥분)."""
    n = int(duration) + 1
    arr = np.zeros(n)
    if not transcript_path.exists():
        return arr
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            sec = int(w.get("start", 0))
            if 0 <= sec < n:
                arr[sec] += 1
    return arr


def window_sum(arr: np.ndarray, win: int) -> np.ndarray:
    """간단한 슬라이딩 합 (length 동일)."""
    if len(arr) == 0:
        return arr
    cum = np.concatenate([[0], np.cumsum(arr)])
    out = np.zeros_like(arr, dtype=float)
    for i in range(len(arr)):
        a = max(0, i - win // 2)
        b = min(len(arr), i + win // 2 + 1)
        out[i] = cum[b] - cum[a]
    return out


def find_peaks(score: np.ndarray, threshold: float) -> list[int]:
    """threshold 이상이고 좌우 N초 안에서 가장 큰 지점만 추출."""
    peaks = []
    i = 0
    while i < len(score):
        if score[i] >= threshold:
            j = min(len(score), i + WINDOW_SEC * 2)
            local_max = i + int(np.argmax(score[i:j]))
            peaks.append(local_max)
            i = local_max + WINDOW_SEC * 2
        else:
            i += 1
    return peaks


def merge_overlapping(intervals: list[tuple[int, int, dict]]) -> list[tuple[int, int, dict]]:
    if not intervals:
        return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for start, end, info in intervals[1:]:
        m_start, m_end, m_info = merged[-1]
        if start <= m_end:
            new_info = {
                "score": max(m_info["score"], info["score"]),
                "reasons": sorted(set(m_info["reasons"]) | set(info["reasons"])),
            }
            merged[-1] = (m_start, max(m_end, end), new_info)
        else:
            merged.append((start, end, info))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    vod = f / "vod.mp4"
    if not vod.exists():
        sys.exit(f"[X] {vod} 없음. chzzk_download.py 먼저 실행.")

    out = f / "signals.json"
    if out.exists() and not args.force:
        print(f"[O] signals.json 이미 존재 → 건너뜀")
        return

    duration = get_duration_seconds(vod)
    print(f"[O] VOD 길이: {duration:.0f}s ({duration/3600:.1f}시간)")

    rms = extract_loudness(vod, duration)
    chat_count, laugh = chat_signals(f / "chat.json", duration)
    word_density = transcript_density(f / "transcript.json", duration)

    # 정규화 (각 신호의 평균 대비 비율로)
    def norm(a: np.ndarray) -> np.ndarray:
        s = window_sum(a, WINDOW_SEC)
        m = s.mean() if s.mean() > 0 else 1.0
        return s / m

    rms_n = norm(rms)
    chat_n = norm(chat_count)
    laugh_n = norm(laugh)
    word_n = norm(word_density)

    # 가중 합산 점수
    composite = (
        rms_n * 1.0 +
        chat_n * 1.5 +
        laugh_n * 2.0 +
        word_n * 0.5
    )

    peaks = find_peaks(composite, threshold=PEAK_RATIO)
    print(f"[O] {len(peaks)}개 피크 감지")

    candidates = []
    for p in peaks:
        # 클립 길이 결정: 피크 주변 신호가 평균 이상인 구간
        left = p
        while left > 0 and composite[left - 1] > 1.2 and (p - left) < (MAX_CLIP - PAD_BEFORE):
            left -= 1
        right = p
        while right < len(composite) - 1 and composite[right + 1] > 1.2 and (right - p) < (MAX_CLIP - PAD_AFTER):
            right += 1

        start = max(0, left - PAD_BEFORE)
        end = min(int(duration), right + PAD_AFTER)
        if (end - start) < MIN_CLIP:
            end = start + MIN_CLIP

        reasons = []
        if rms_n[p] > PEAK_RATIO: reasons.append("volume_peak")
        if chat_n[p] > PEAK_RATIO: reasons.append("chat_burst")
        if laugh_n[p] > PEAK_RATIO: reasons.append("laughter")
        if word_n[p] > PEAK_RATIO: reasons.append("rapid_speech")
        if not reasons:
            reasons.append("composite")

        score = int(min(100, composite[p] * 20))
        candidates.append((start, end, {"score": score, "reasons": reasons}))

    merged = merge_overlapping(candidates)

    payload = {
        "version": 1,
        "duration": duration,
        "params": {
            "window_sec": WINDOW_SEC,
            "peak_ratio": PEAK_RATIO,
            "min_clip": MIN_CLIP,
            "max_clip": MAX_CLIP,
        },
        "candidates": [
            {"start": s, "end": e, **info}
            for s, e, info in merged
        ],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[O] {len(merged)}개 후보 → {out}")


if __name__ == "__main__":
    main()
