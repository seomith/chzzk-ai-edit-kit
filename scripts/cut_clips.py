"""
cut_clips.py — highlights.json 기반으로 ffmpeg 자동 컷

사용법:
    python scripts/cut_clips.py 260504
    python scripts/cut_clips.py 260504 --skip-shorts   # 쇼츠 컷 생략
    python scripts/cut_clips.py 260504 --longform-only # 롱폼만
    python scripts/cut_clips.py 260504 --export-edl    # 다빈치/프리미어용 EDL도 생성

입력:
    <YYMMDD>/vod.mp4
    <YYMMDD>/highlights.json

출력:
    <YYMMDD>/clips/sNN_<title>.mp4   (쇼츠 후보, 16:9 원본 비율)
    <YYMMDD>/longform/highlight_full.mp4  (하이라이트 모음)
    <YYMMDD>/longform/chapters.txt        (유튜브 챕터)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def folder(yymmdd: str) -> Path:
    p = Path(yymmdd)
    if not p.exists():
        sys.exit(f"[X] 폴더 없음: {p.resolve()}")
    return p


def load_highlights(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"[X] {path} 없음. AI 스크리닝 단계에서 만들어야 합니다.\n"
                 f"    AI 어시스턴트에 'highlights.json 만들어줘' 라고 요청하세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s[:50]


def hms(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def cut_clip(vod: Path, start: float, end: float, out: Path) -> None:
    """단일 클립 추출. 정확한 컷을 위해 재인코딩 (느리지만 안전)."""
    duration = end - start
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(vod),
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print(f"[X] ffmpeg 실패: {out.name}")
        print(res.stderr.decode("utf-8", errors="replace")[-500:])
        return
    print(f"  + {out.name}  ({hms(start)} ~ {hms(end)}, {duration:.0f}s)")


def cut_shorts_candidates(vod: Path, hl: dict, out_dir: Path) -> None:
    print(f"[.] 쇼츠 후보 {len(hl.get('shorts', []))}개 컷 중...")
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, item in enumerate(hl.get("shorts", []), 1):
        idx = item.get("id", f"s{i:02d}")
        title = safe_name(item.get("title") or f"clip_{i:02d}")
        out = out_dir / f"{idx}_{title}.mp4"
        cut_clip(vod, item["start"], item["end"], out)


def cut_longform(vod: Path, hl: dict, out_dir: Path) -> None:
    chapters = hl.get("longform_chapters", [])
    included = [c for c in chapters if c.get("include_in_highlight")]
    if not included:
        print(f"[!] 롱폼 포함 챕터 없음 — 건너뜀")
        return

    print(f"[.] 롱폼 하이라이트 {len(included)}개 챕터 컷팅 중...")
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, c in enumerate(included, 1):
        part = out_dir / f"_part{i:02d}.mp4"
        cut_clip(vod, c["start"], c["end"], part)
        parts.append(part)

    # concat
    concat_list = out_dir / "_concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.name}'" for p in parts),
        encoding="utf-8",
    )
    final = out_dir / "highlight_full.mp4"
    print(f"[.] 챕터 합치는 중 → {final.name}")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(final),
    ]
    res = subprocess.run(cmd, capture_output=True)
    if res.returncode != 0:
        print("[X] concat 실패")
        print(res.stderr.decode("utf-8", errors="replace")[-500:])
        return

    # 챕터 마크 (유튜브 설명란용)
    chap_path = out_dir / "chapters.txt"
    lines = []
    cursor = 0
    for c in included:
        title = c.get("title") or "(무제)"
        lines.append(f"{hms(cursor)} {title}")
        cursor += int(c["end"] - c["start"])
    chap_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[O] 롱폼: {final}")
    print(f"[O] 챕터: {chap_path}")

    # 임시 파일 정리
    for p in parts:
        p.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)


def export_edl(hl: dict, out_path: Path) -> None:
    """단순 EDL (CMX3600 호환). 다빈치 무료에서 import 가능.
    참고: EDL은 프레임 단위라 30fps 가정.
    """
    fps = 30
    def to_tc(sec: float) -> str:
        f = int(sec * fps)
        h = f // (3600 * fps)
        m = (f % (3600 * fps)) // (60 * fps)
        s = (f % (60 * fps)) // fps
        ff = f % fps
        return f"{h:02d}:{m:02d}:{s:02d}:{ff:02d}"

    lines = ["TITLE: AI Highlights", "FCM: NON-DROP FRAME", ""]
    rec = 0.0
    for i, item in enumerate(hl.get("shorts", []) + hl.get("longform_chapters", []), 1):
        if "start" not in item or "end" not in item:
            continue
        dur = item["end"] - item["start"]
        lines.append(
            f"{i:03d}  AX       V     C        "
            f"{to_tc(item['start'])} {to_tc(item['end'])} "
            f"{to_tc(rec)} {to_tc(rec + dur)}"
        )
        lines.append(f"* FROM CLIP NAME: {item.get('title', '')}")
        rec += dur
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[O] EDL 내보냄: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--skip-shorts", action="store_true")
    ap.add_argument("--longform-only", action="store_true")
    ap.add_argument("--shorts-only", action="store_true")
    ap.add_argument("--export-edl", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    vod = f / "vod.mp4"
    hl = load_highlights(f / "highlights.json")

    if not args.longform_only and not args.skip_shorts:
        cut_shorts_candidates(vod, hl, f / "clips")
    if not args.shorts_only:
        cut_longform(vod, hl, f / "longform")
    if args.export_edl:
        export_edl(hl, f / "edit.edl")

    print(f"[O] 컷 완료. 다음: python scripts/make_shorts.py {args.yymmdd}")


if __name__ == "__main__":
    main()
