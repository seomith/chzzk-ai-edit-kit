"""
batch_process.py — 미처리 폴더 일괄 파이프라인 실행

사용법:
    python scripts/batch_process.py
    python scripts/batch_process.py --root C:\\Users\\Me\\방송
    python scripts/batch_process.py --skip-existing  # 기본값
    python scripts/batch_process.py --since 260501

규칙:
    - YYMMDD 형식 폴더만 대상
    - shorts/ 폴더가 비어 있으면 "미처리"로 간주
    - source.url 없으면 건너뜀
    - AI 스크리닝(4단계)은 자동화하지 않음 — highlights.json 없으면 안내만
      → AI 어시스턴트가 그 단계만 따로 진행
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

YYMMDD_RE = re.compile(r"^\d{6}$")


def is_target(folder: Path, since: str | None) -> bool:
    if not folder.is_dir() or not YYMMDD_RE.match(folder.name):
        return False
    if since and folder.name < since:
        return False
    has_input = any((folder / x).exists() for x in ("source.url", "source.video", "vod.mp4"))
    if not has_input:
        return False
    shorts = folder / "shorts"
    if shorts.exists() and any(shorts.glob("*.mp4")):
        return False
    return True


def run(cmd: list[str]) -> bool:
    print(f"\n>>> {' '.join(cmd)}")
    res = subprocess.run(cmd)
    return res.returncode == 0


def process_one(yymmdd: str, scripts: Path) -> str:
    """한 폴더 처리. 반환: 'ok' / 'needs_screening' / 'failed'"""
    folder = Path(yymmdd)

    steps: list[tuple[str, list[str]]] = []
    # 영상 입력이 source.url 인 경우만 다운로드. OBS 녹화본 사용자는 스킵.
    if (folder / "source.url").exists():
        steps.append(("download", ["python", str(scripts / "chzzk_download.py"), yymmdd]))
    else:
        print(f"[i] {yymmdd}: source.url 없음 → 다운로드 스킵 (vod.mp4 / source.video 가정)")

    steps += [
        ("transcribe", ["python", str(scripts / "transcribe.py"), yymmdd]),
        ("correct", ["python", str(scripts / "correct_transcript.py"), yymmdd]),
        ("analyze", ["python", str(scripts / "analyze_signals.py"), yymmdd]),
    ]
    for name, cmd in steps:
        if not run(cmd):
            print(f"[X] {yymmdd} {name} 단계 실패")
            return "failed"

    if not (folder / "highlights.json").exists():
        print(f"[!] {yymmdd}: highlights.json 없음 — AI 스크리닝 필요")
        print(f"    AI 어시스턴트에 '{yymmdd} 하이라이트 뽑아줘' 요청하세요.")
        return "needs_screening"

    final_steps = [
        ("cut", ["python", str(scripts / "cut_clips.py"), yymmdd]),
        ("shorts", ["python", str(scripts / "make_shorts.py"), yymmdd]),
    ]
    for name, cmd in final_steps:
        if not run(cmd):
            print(f"[X] {yymmdd} {name} 단계 실패")
            return "failed"
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="작업 루트 (기본: 현재 폴더)")
    ap.add_argument("--since", help="이 날짜(YYMMDD) 이후만")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    args = ap.parse_args()

    root = Path(args.root)
    targets = sorted(p for p in root.iterdir() if is_target(p, args.since))
    if not targets:
        print("처리할 폴더 없음.")
        return

    print(f"== 일괄 처리 대상: {len(targets)}개 ==")
    for p in targets:
        print(f"  - {p.name}")

    scripts = Path(__file__).parent
    results: list[tuple[str, str]] = []
    for p in targets:
        print(f"\n========== {p.name} 시작 ==========")
        try:
            r = process_one(p.name, scripts)
        except Exception as e:
            print(f"[X] 예외: {e}")
            r = "failed"
        results.append((p.name, r))

    print("\n== 결과 ==")
    for name, r in results:
        mark = {"ok": "[O]", "needs_screening": "[~]", "failed": "[X]"}[r]
        print(f"  {mark} {name}: {r}")


if __name__ == "__main__":
    main()
