"""
make_shorts.py — clips/*.mp4 → shorts/*.mp4 (9:16 + 자막 burn-in)

사용법:
    python scripts/make_shorts.py 260504
    python scripts/make_shorts.py 260504 --no-subs    # 자막 없이
    python scripts/make_shorts.py 260504 --crop center # 중앙 크롭 (기본)

크롭 모드:
    - center: 중앙 9:16 (기본)
    - blur:   원본 16:9를 위에 두고 위아래에 블러 배경 (캠 위치 무관)

자막:
    transcript.json에서 클립 시간 범위 텍스트를 추출해 ASS로 burn-in.
    톤: 큼지막한 흰 글씨 + 검은 외곽선 (예능 스타일)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from _common import folder


def parse_clip_time(name: str) -> tuple[str, str] | None:
    return None  # 클립 파일에 시간 메타가 없으면 highlights.json에서 매칭


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


def make_ass_subs(transcript: dict, start: float, end: float, out_ass: Path) -> bool:
    """클립 구간 자막을 ASS로 작성. burn-in용 큰 글씨 스타일."""
    if not transcript:
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
    for seg in transcript.get("segments", []):
        if seg["end"] < start or seg["start"] > end:
            continue
        # 클립 기준 시간으로 변환
        s = max(0, seg["start"] - start)
        e = min(end - start, seg["end"] - start)
        text = seg["text"].replace("\n", " ").strip()
        if not text:
            continue
        # 너무 길면 줄바꿈
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
        # 위아래 블러 배경, 가운데 원본
        vf = (
            "split[main][bg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=20:5[bg2];"
            "[main]scale=1080:-1[fg];"
            "[bg2][fg]overlay=(W-w)/2:(H-h)/2"
        )
    else:
        # 중앙 크롭 (입력이 16:9라고 가정)
        vf = "crop=ih*9/16:ih,scale=1080:1920"

    if ass_path and ass_path.exists():
        # ASS 경로의 백슬래시·콜론 이스케이프 (윈도우)
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
    """쇼츠 클립 옆에 메타데이터 텍스트 파일 (제목/태그/설명)."""
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
    ap.add_argument("--no-subs", action="store_true")
    ap.add_argument("--crop", default="center", choices=["center", "blur"])
    args = ap.parse_args()

    f = folder(args.yymmdd)
    clips_dir = f / "clips"
    if not clips_dir.exists():
        sys.exit(f"[X] {clips_dir} 없음. cut_clips.py 먼저 실행.")

    shorts_dir = f / "shorts"
    shorts_dir.mkdir(parents=True, exist_ok=True)

    hl = load_highlights(f / "highlights.json")
    if not args.no_subs:
        transcript, src_name = load_transcript_for_subs(f)
        if src_name:
            print(f"[O] 자막 소스: {src_name}")
    else:
        transcript = {}
    by_id = {item.get("id"): item for item in hl.get("shorts", [])}

    clip_files = sorted(clips_dir.glob("*.mp4"))
    if not clip_files:
        sys.exit(f"[X] 클립 없음: {clips_dir}")

    print(f"[.] {len(clip_files)}개 쇼츠 변환 중 ({args.crop} 모드)")

    for clip in clip_files:
        # 파일명 첫 토큰이 id (예: s01_제목.mp4)
        m = re.match(r"^([a-z]\d+)_", clip.name)
        clip_id = m.group(1) if m else None
        item = by_id.get(clip_id, {})

        out = shorts_dir / clip.name.replace(".mp4", "_shorts.mp4")
        ass_path = shorts_dir / f"_{clip.stem}.ass" if not args.no_subs else None

        if ass_path:
            ok = make_ass_subs(transcript,
                               item.get("start", 0),
                               item.get("end", 0),
                               ass_path)
            if not ok:
                ass_path = None

        reframe_to_vertical(clip, out, ass_path, crop_mode=args.crop)

        if ass_path:
            ass_path.unlink(missing_ok=True)

        if item:
            write_meta(item, shorts_dir / out.name.replace(".mp4", ".txt"))

    print(f"[O] 완료. {shorts_dir}/ 에서 결과 확인 후 NG는 _NG_ 접두사로 표시.")


if __name__ == "__main__":
    main()
