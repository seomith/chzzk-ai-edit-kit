"""
cut_clips.py — highlights.json 기반으로 ffmpeg 자동 컷 + 결과 요약

사용법:
    python scripts/cut_clips.py 260504
    python scripts/cut_clips.py 260504 --shorts-limit 10  # 점수 상위 10개
    python scripts/cut_clips.py 260504 --shorts-limit 0   # 전체
    python scripts/cut_clips.py 260504 --skip-shorts
    python scripts/cut_clips.py 260504 --longform-only
    python scripts/cut_clips.py 260504 --export-edl       # 다빈치/프리미어용 EDL

동작:
    - 쇼츠는 점수 내림차순 정렬 후 상위 N개만 컷 (기본 5)
    - 롱폼은 include_in_highlight 챕터들을 합쳐 highlight_full.mp4 1개
    - warnings 는 mp4 생성 안 함 (목록만)
    - 모든 결과를 <YYMMDD>/summary.md 한 파일로 정리
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from _common import folder, resolve_vod_path

SHORTS_LIMIT_DEFAULT = 5


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
    sec = int(sec or 0)
    return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"


def cut_clip(vod: Path, start: float, end: float, out: Path) -> bool:
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
        return False
    print(f"  + {out.name}  ({hms(start)} ~ {hms(end)}, {duration:.0f}s)")
    return True


def cut_shorts_candidates(vod: Path, hl: dict, out_dir: Path,
                          limit: int) -> tuple[list[dict], list[dict]]:
    """점수 내림차순 상위 limit개만 컷. (made, skipped) 반환.
    limit=0 이면 전체.
    """
    items = hl.get("shorts", []) or []
    sorted_items = sorted(items, key=lambda x: -(x.get("score") or 0))
    if limit > 0:
        to_cut = sorted_items[:limit]
        skipped = sorted_items[limit:]
    else:
        to_cut, skipped = sorted_items, []

    print(f"[.] 쇼츠 후보 {len(items)}개 중 {len(to_cut)}개 컷 (--shorts-limit {limit})")
    out_dir.mkdir(parents=True, exist_ok=True)
    made: list[dict] = []
    for i, item in enumerate(to_cut, 1):
        idx = item.get("id", f"s{i:02d}")
        title = safe_name(item.get("title") or f"clip_{i:02d}")
        out = out_dir / f"{idx}_{title}.mp4"
        if cut_clip(vod, item["start"], item["end"], out):
            made.append({**item, "_file": out.name})
    return made, skipped


def cut_longform(vod: Path, hl: dict, out_dir: Path) -> bool:
    chapters = hl.get("longform_chapters", []) or []
    included = [c for c in chapters if c.get("include_in_highlight")]
    if not included:
        print(f"[!] 롱폼 포함 챕터 없음 — 건너뜀")
        return False

    print(f"[.] 롱폼 하이라이트 {len(included)}개 챕터 컷팅 중...")
    out_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, c in enumerate(included, 1):
        part = out_dir / f"_part{i:02d}.mp4"
        if cut_clip(vod, c["start"], c["end"], part):
            parts.append(part)
    if not parts:
        return False

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
        return False

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

    for p in parts:
        p.unlink(missing_ok=True)
    concat_list.unlink(missing_ok=True)
    return True


def export_edl(hl: dict, out_path: Path) -> None:
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
    for i, item in enumerate((hl.get("shorts") or []) + (hl.get("longform_chapters") or []), 1):
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


def write_summary_md(work_folder: Path, hl: dict,
                     made_shorts: list[dict], skipped_shorts: list[dict],
                     longform_made: bool, shorts_limit: int) -> Path:
    lines: list[str] = []
    lines.append(f"# {work_folder.name} 방송 — 처리 결과")
    lines.append("")

    meta_path = work_folder / "meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            lines.append(f"- 제목: {meta.get('title') or '(미상)'}")
            lines.append(f"- 채널: {meta.get('channel_name') or '(미상)'}")
            if meta.get('duration'):
                lines.append(f"- 길이: {hms(meta.get('duration'))}")
        except Exception:
            pass
    lines.append(f"- 처리 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 쇼츠 한도: {shorts_limit if shorts_limit > 0 else '제한 없음'}")
    lines.append("")

    # 쇼츠
    lines.append("## 쇼츠")
    lines.append("")
    lines.append(f"### 만든 것 ({len(made_shorts)}개) — `shorts/` 에 mp4 + 메타 .txt")
    lines.append("")
    if made_shorts:
        lines.append("| ID | 시간 | 제목 | 점수 | 파일 |")
        lines.append("|---|---|---|---|---|")
        for s in made_shorts:
            lines.append(
                f"| {s.get('id', '-')} "
                f"| {hms(s.get('start'))}~{hms(s.get('end'))} "
                f"| {s.get('title', '-')} "
                f"| {s.get('score', '-')} "
                f"| `{s.get('_file', '-')}` |"
            )
    else:
        lines.append("(없음)")
    lines.append("")

    if skipped_shorts:
        lines.append(f"### 만들지 않은 후보 ({len(skipped_shorts)}개)")
        lines.append("")
        lines.append("> 추가하려면 AI에 `\"sNN, sMM 쇼츠로 만들어줘\"` 또는 ")
        lines.append("> `python scripts/cut_clips.py {} --shorts-limit N` 으로 한도 늘려 재실행".format(work_folder.name))
        lines.append("")
        lines.append("| ID | 시간 | 제목 | 점수 | 사유 |")
        lines.append("|---|---|---|---|---|")
        for s in skipped_shorts:
            reason = (s.get('reason') or '').replace('|', '/').replace('\n', ' ')
            lines.append(
                f"| {s.get('id', '-')} "
                f"| {hms(s.get('start'))}~{hms(s.get('end'))} "
                f"| {s.get('title', '-')} "
                f"| {s.get('score', '-')} "
                f"| {reason} |"
            )
        lines.append("")

    # 롱폼
    lines.append("## 롱폼")
    lines.append("")
    chapters = hl.get("longform_chapters") or []
    included = [c for c in chapters if c.get("include_in_highlight")]
    if longform_made:
        total = sum((c.get("end", 0) - c.get("start", 0)) for c in included)
        lines.append(f"- `longform/highlight_full.mp4` (포함 챕터 {len(included)}개, 총 {hms(total)})")
        lines.append("- `longform/chapters.txt` (유튜브 설명란용)")
    else:
        lines.append("- (생성 안 됨 — `include_in_highlight: true` 챕터 없음 또는 `--shorts-only`)")
    lines.append("")

    if chapters:
        lines.append("### 전체 챕터 (포함/제외)")
        lines.append("")
        for c in chapters:
            mark = "[O]" if c.get("include_in_highlight") else "[ ]"
            lines.append(f"- {mark} `{hms(c.get('start'))}` {c.get('title', '-')}")
        lines.append("")

    # warnings
    warnings = hl.get("warnings") or []
    if warnings:
        lines.append("## ⚠ 검수 필요 (mp4 안 만듦, 사람 확인)")
        lines.append("")
        lines.append("| 시간 | 종류 | 메모 |")
        lines.append("|---|---|---|")
        for w in warnings:
            note = (w.get('note') or '').replace('|', '/').replace('\n', ' ')
            lines.append(
                f"| {hms(w.get('start'))}~{hms(w.get('end'))} "
                f"| {w.get('type', '-')} "
                f"| {note} |"
            )
        lines.append("")
    else:
        lines.append("## ⚠ 검수 필요")
        lines.append("")
        lines.append("(없음)")
        lines.append("")

    # 다음 액션
    lines.append("## 다음 액션")
    lines.append("")
    name = work_folder.name
    lines.append(f"1. 탐색기에서 `{name}/shorts/*.mp4` ({len(made_shorts)}개) 미리보기 → NG는 파일명 앞에 `_NG_` 접두사")
    if longform_made:
        lines.append(f"2. `{name}/longform/highlight_full.mp4` 확인 (필요하면 `chapters.txt` 를 유튜브 설명란에 붙여넣기)")
    if warnings:
        lines.append(f"3. ⚠ 검수 필요 항목 ({len(warnings)}개) 직접 시점 이동해서 확인")
    lines.append(f"4. 업로드 메타데이터(제목/태그/설명)는 `{name}/shorts/*.txt` 에 같이 들어 있음")
    if skipped_shorts:
        lines.append(f"5. (선택) 미생성 후보 {len(skipped_shorts)}개 중 끌리는 ID 가 있으면 AI 에 추가 컷 요청")
    lines.append("")

    out = work_folder / "summary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[O] summary: {out}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--shorts-limit", type=int, default=SHORTS_LIMIT_DEFAULT,
                    help=f"점수 상위 N개만 컷 (기본 {SHORTS_LIMIT_DEFAULT}, 0=제한 없음)")
    ap.add_argument("--skip-shorts", action="store_true")
    ap.add_argument("--longform-only", action="store_true")
    ap.add_argument("--shorts-only", action="store_true")
    ap.add_argument("--export-edl", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    vod = resolve_vod_path(f)
    hl = load_highlights(f / "highlights.json")

    made_shorts: list[dict] = []
    skipped_shorts: list[dict] = []
    if not args.longform_only and not args.skip_shorts:
        made_shorts, skipped_shorts = cut_shorts_candidates(
            vod, hl, f / "clips", args.shorts_limit,
        )

    longform_made = False
    if not args.shorts_only:
        longform_made = cut_longform(vod, hl, f / "longform")

    if args.export_edl:
        export_edl(hl, f / "edit.edl")

    write_summary_md(f, hl, made_shorts, skipped_shorts, longform_made, args.shorts_limit)

    print(f"[O] 컷 완료. 다음: python scripts/make_shorts.py {args.yymmdd}")


if __name__ == "__main__":
    main()
