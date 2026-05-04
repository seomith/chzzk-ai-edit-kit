"""
make_shorts.py — clips/*.mp4 → shorts/*.mp4 (9:16) + 자막 사이드 파일

기본 동작:
    - 9:16 리프레임
    - .srt 자막 사이드 파일을 영상 옆에 같이 출력 (--no-keep-subs 로 끄기)
    - 자막 burn-in 은 OFF (사용자가 --burn-subs 로 명시한 경우에만 박음)

이유:
    자막 품질이 STT 모델·교정 상태에 따라 들쑥날쑥하므로 기본 burn-in 은 위험.
    .srt 사이드 파일이면 프리미어/다빈치 import, 유튜브 자막 직접 업로드,
    필요 시 사용자가 직접 burn-in 하는 등 운용이 자유로움.

사용법:
    python scripts/make_shorts.py 260504                         # 영상 + .srt
    python scripts/make_shorts.py 260504 --burn-subs             # 영상에 자막 박기
    python scripts/make_shorts.py 260504 --no-keep-subs          # .srt 도 안 만듦
    python scripts/make_shorts.py 260504 --no-subs               # 둘 다 OFF (=영상만)
    python scripts/make_shorts.py 260504 --crop blur             # 위아래 블러 배경

크롭 모드:
    - center: 중앙 9:16 (기본)
    - blur:   원본 16:9를 위에 두고 위아래에 블러 배경 (캠 위치 무관)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from _common import folder


def load_highlights(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_transcript_for_subs(work_folder: Path) -> tuple[dict, str]:
    """자막용 transcript 로드. corrected 가 있으면 우선.
    corrected segment 의 corrected_text 를 표준 text 로 정규화해서 반환.
    """
    corrected = work_folder / "transcript.corrected.json"
    raw = work_folder / "transcript.json"
    if corrected.exists():
        data = json.loads(corrected.read_text(encoding="utf-8"))
        for seg in data.get("segments", []):
            if "corrected_text" in seg:
                seg["text"] = seg["corrected_text"]
        return data, "transcript.corrected.json"
    if raw.exists():
        return json.loads(raw.read_text(encoding="utf-8")), "transcript.json"
    return {}, ""


def _segments_in_range(transcript: dict, start: float, end: float) -> list[dict]:
    out = []
    for seg in transcript.get("segments", []):
        s, e = seg.get("start"), seg.get("end")
        if s is None or e is None:
            continue
        if e < start or s > end:
            continue
        out.append(seg)
    return out


def _srt_time(t: float) -> str:
    """SRT 시간 형식: HH:MM:SS,mmm (콤마)"""
    t = max(0.0, float(t))
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int(round((t - int(t)) * 1000))
    if ms == 1000:
        s += 1; ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_srt(transcript: dict, start: float, end: float, out_srt: Path) -> bool:
    """클립 구간을 SRT 자막으로 저장. 시간은 클립 기준(0초부터)으로 변환."""
    segs = _segments_in_range(transcript, start, end)
    if not segs:
        return False
    lines = []
    idx = 0
    for seg in segs:
        s = max(0.0, seg["start"] - start)
        e = min(end - start, seg["end"] - start)
        if e <= s:
            continue
        text = (seg.get("text") or "").replace("\n", " ").strip()
        if not text:
            continue
        idx += 1
        lines.append(str(idx))
        lines.append(f"{_srt_time(s)} --> {_srt_time(e)}")
        lines.append(text)
        lines.append("")
    if idx == 0:
        return False
    out_srt.write_text("\n".join(lines), encoding="utf-8")
    return True


def make_ass_subs(transcript: dict, start: float, end: float, out_ass: Path) -> bool:
    """클립 구간 자막을 ASS 로 작성. burn-in 용 큰 글씨 스타일."""
    segs = _segments_in_range(transcript, start, end)
    if not segs:
        return False

    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Malgun Gothic,72,&H00FFFFFF,&H00000000,&H80000000,1,0,1,5,0,2,40,40,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def fmt(t: float) -> str:
        t = max(0, t)
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:01d}:{m:02d}:{s:05.2f}"

    lines = []
    for seg in segs:
        s = max(0, seg["start"] - start)
        e = min(end - start, seg["end"] - start)
        text = seg["text"].replace("\n", " ").strip()
        if not text:
            continue
        if len(text) > 18:
            mid = len(text) // 2
            sp = text.rfind(" ", 0, mid)
            if sp > 0:
                text = text[:sp] + r"\N" + text[sp + 1:]
        lines.append(f"Dialogue: 0,{fmt(s)},{fmt(e)},Default,,0,0,0,,{text}")

    if not lines:
        return False
    out_ass.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    return True


def reframe_to_vertical(in_clip: Path, out_path: Path, ass_path: Path | None,
                        crop_mode: str = "center") -> None:
    """16:9 → 9:16 변환 + (선택) 자막 burn-in."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if crop_mode == "blur":
        vf = (
            "split[main][bg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=20:5[bg2];"
            "[main]scale=1080:-1[fg];"
            "[bg2][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        vf = "crop=ih*9/16:ih,scale=1080:1920"

    if ass_path and ass_path.exists():
        ass_str = str(ass_path).replace("\\", "/").replace(":", r"\:")
        vf += f",ass='{ass_str}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_clip),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-r", "30",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print(f"[X] 쇼츠 변환 실패: {out_path.name}")
        print(res.stderr.decode("utf-8", errors="replace")[-800:])
        return
    print(f"  + {out_path.name}")


def write_meta(item: dict, out_path: Path) -> None:
    title = item.get("title", "")
    tags = ", ".join(item.get("tags", []))
    reason = item.get("reason", "")
    body = (
        f"제목: {title}\n"
        f"태그: {tags}\n"
        f"\n"
        f"설명:\n{title}\n"
        f"\n"
        f"#쇼츠 #{tags.replace(', ', ' #')}\n"
        f"\n"
        f"---\n"
        f"AI 분석 사유: {reason}\n"
    )
    out_path.write_text(body, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--burn-subs", action="store_true",
                    help="자막을 영상에 박기 (기본 OFF — 자막 품질 검증 후 사용 권장)")
    ap.add_argument("--no-keep-subs", action="store_true",
                    help=".srt 사이드 파일도 만들지 않음")
    ap.add_argument("--no-subs", action="store_true",
                    help="자막 관련 모든 출력 OFF (= burn 안 함 + .srt 안 만듦)")
    ap.add_argument("--crop", default="center", choices=["center", "blur"])
    args = ap.parse_args()

    keep_srt = not args.no_keep_subs and not args.no_subs
    burn_in = args.burn_subs and not args.no_subs

    f = folder(args.yymmdd)
    clips_dir = f / "clips"
    if not clips_dir.exists():
        sys.exit(f"[X] {clips_dir} 없음. cut_clips.py 먼저 실행.")

    shorts_dir = f / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    hl = load_highlights(f / "highlights.json")
    transcript: dict = {}
    if keep_srt or burn_in:
        transcript, src_name = load_transcript_for_subs(f)
        if src_name:
            print(f"[O] 자막 소스: {src_name}")
        else:
            print("[!] transcript 없음 — 자막 출력 생략")
            transcript = {}

    by_id = {item.get("id"): item for item in hl.get("shorts", [])}

    clip_files = sorted(clips_dir.glob("*.mp4"))
    if not clip_files:
        sys.exit(f"[X] 클립 없음: {clips_dir}")

    mode_label = []
    if burn_in: mode_label.append("burn-in")
    if keep_srt: mode_label.append(".srt")
    if not mode_label: mode_label.append("자막 없음")
    print(f"[.] {len(clip_files)}개 쇼츠 변환 중 (crop={args.crop}, 자막={'+'.join(mode_label)})")

    for clip in clip_files:
        m = re.match(r"^([a-z]\d+)_", clip.name)
        clip_id = m.group(1) if m else None
        item = by_id.get(clip_id, {})

        out = shorts_dir / clip.name.replace(".mp4", "_shorts.mp4")
        start = item.get("start", 0)
        end = item.get("end", 0)

        # burn-in 용 임시 ASS
        ass_path: Path | None = None
        if burn_in and transcript:
            ass_path = shorts_dir / f"_{clip.stem}.ass"
            if not make_ass_subs(transcript, start, end, ass_path):
                ass_path = None

        reframe_to_vertical(clip, out, ass_path, crop_mode=args.crop)

        if ass_path:
            ass_path.unlink(missing_ok=True)

        # .srt 사이드 파일 (영상과 같은 베이스명)
        if keep_srt and transcript:
            srt_path = out.with_suffix(".srt")
            ok = make_srt(transcript, start, end, srt_path)
            if ok:
                print(f"    .srt: {srt_path.name}")

        if item:
            write_meta(item, shorts_dir / out.name.replace(".mp4", ".txt"))

    print(f"[O] 완료. {shorts_dir}/ 에서 결과 확인 후 NG는 _NG_ 접두사로 표시.")
    if not burn_in and keep_srt:
        print("    자막은 .srt 사이드 파일로 동봉됨 — 유튜브 업로드 시 자막 파일로 첨부하거나, ")
        print("    프리미어/다빈치에 import. 자막을 영상에 박으려면 --burn-subs 로 재실행.")


if __name__ == "__main__":
    main()
