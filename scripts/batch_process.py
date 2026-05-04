"""
batch_process.py — OBS 녹화 폴더/작업 폴더에서 미처리 회차 일괄 실행

사용법:
    python scripts/batch_process.py
    python scripts/batch_process.py --root D:\\OBS\\녹화
    python scripts/batch_process.py --root C:\\Users\\Me\\방송작업 --work-root C:\\Users\\Me\\방송작업
    python scripts/batch_process.py --skip-existing  # 기본값
    python scripts/batch_process.py --since 260501

규칙:
    - --root 아래의 YYMMDD 형식 폴더 또는 날짜가 들어간 OBS 영상 파일을 대상
    - OBS 영상 파일은 <work-root>/YYMMDD/source.video 로 연결
    - shorts/ 폴더가 비어 있으면 "미처리"로 간주
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
YYMMDD_IN_NAME_RE = re.compile(r"(?<!\d)(\d{6})(?!\d)")
VIDEO_EXTS = {".mp4", ".mkv", ".mov"}


def is_unprocessed_work_folder(folder: Path, since: str | None) -> bool:
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


def infer_yymmdd(path: Path) -> str | None:
    m = YYMMDD_IN_NAME_RE.search(path.stem)
    return m.group(1) if m else None


def discover_work_folders(root: Path, since: str | None) -> list[Path]:
    return sorted(p for p in root.iterdir() if is_unprocessed_work_folder(p, since))


def discover_obs_videos(root: Path, since: str | None) -> list[Path]:
    videos: list[Path] = []
    for p in root.iterdir():
        if not p.is_file() or p.suffix.lower() not in VIDEO_EXTS:
            continue
        yymmdd = infer_yymmdd(p)
        if not yymmdd:
            continue
        if since and yymmdd < since:
            continue
        videos.append(p)
    return sorted(videos)


def ensure_work_folder_from_video(video: Path, work_root: Path) -> Path:
    yymmdd = infer_yymmdd(video)
    if not yymmdd:
        raise ValueError(f"파일명에서 YYMMDD 날짜를 찾지 못함: {video.name}")
    work = work_root / yymmdd
    work.mkdir(parents=True, exist_ok=True)
    src = work / "source.video"
    if not src.exists():
        src.write_text(str(video.resolve()), encoding="utf-8")
        print(f"[O] {work.name}/source.video 작성: {video.resolve()}")
    return work


def run(cmd: list[str], cwd: Path) -> bool:
    print(f"\n>>> {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=cwd)
    return res.returncode == 0


def process_one(work_folder: Path, scripts: Path) -> str:
    """한 폴더 처리. 반환: 'ok' / 'needs_screening' / 'failed'"""
    yymmdd = work_folder.name
    work_root = work_folder.parent

    steps: list[tuple[str, list[str]]] = []
    # 영상 입력이 source.url 인 경우만 다운로드. OBS 녹화본 사용자는 스킵.
    if (work_folder / "source.url").exists():
        steps.append(("download", ["python", str(scripts / "chzzk_download.py"), yymmdd]))
    else:
        print(f"[i] {yymmdd}: source.url 없음 → 다운로드 스킵 (vod.mp4 / source.video 가정)")

    steps += [
        ("transcribe", ["python", str(scripts / "transcribe.py"), yymmdd]),
        ("correct", ["python", str(scripts / "correct_transcript.py"), yymmdd]),
        ("analyze", ["python", str(scripts / "analyze_signals.py"), yymmdd]),
    ]
    for name, cmd in steps:
        if not run(cmd, cwd=work_root):
            print(f"[X] {yymmdd} {name} 단계 실패")
            return "failed"

    if not (work_folder / "highlights.json").exists():
        print(f"[!] {yymmdd}: highlights.json 없음 — AI 스크리닝 필요")
        print(f"    AI 어시스턴트에 '{yymmdd} 하이라이트 뽑아줘' 요청하세요.")
        return "needs_screening"

    final_steps = [
        ("cut", ["python", str(scripts / "cut_clips.py"), yymmdd]),
        ("shorts", ["python", str(scripts / "make_shorts.py"), yymmdd]),
    ]
    for name, cmd in final_steps:
        if not run(cmd, cwd=work_root):
            print(f"[X] {yymmdd} {name} 단계 실패")
            return "failed"
    return "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".",
                    help="OBS 녹화본 폴더 또는 YYMMDD 작업 폴더들이 있는 루트")
    ap.add_argument("--work-root",
                    help="YYMMDD 작업 폴더를 만들 위치 (기본: YYMMDD 폴더가 있으면 --root, 아니면 현재 폴더)")
    ap.add_argument("--since", help="이 날짜(YYMMDD) 이후만")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        sys.exit(f"[X] root 폴더가 없습니다: {root}")

    work_folders = discover_work_folders(root, args.since)
    if args.work_root:
        work_root = Path(args.work_root).resolve()
    else:
        work_root = root if work_folders else Path.cwd().resolve()
    work_root.mkdir(parents=True, exist_ok=True)

    video_targets = discover_obs_videos(root, args.since)
    for video in video_targets:
        work = ensure_work_folder_from_video(video, work_root)
        if is_unprocessed_work_folder(work, args.since) and work not in work_folders:
            work_folders.append(work)

    targets = sorted(work_folders, key=lambda p: p.name)
    if not targets:
        print("처리할 폴더 없음.")
        return

    print(f"== 일괄 처리 대상: {len(targets)}개 ==")
    print(f"== 입력 root: {root} ==")
    print(f"== 작업 root: {work_root} ==")
    for p in targets:
        print(f"  - {p}")

    scripts = Path(__file__).parent
    results: list[tuple[str, str]] = []
    for p in targets:
        print(f"\n========== {p.name} 시작 ==========")
        try:
            r = process_one(p, scripts)
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
