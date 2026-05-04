"""
_common.py — 모든 스크립트가 공유하는 작은 헬퍼.

- folder(yymmdd): 작업 폴더 경로 검증·반환
- resolve_vod_path(folder): 영상 파일 경로 결정
    1) source.video 파일이 있으면 그 안의 절대경로 사용 (OBS 녹화본 등)
    2) 없으면 폴더 안의 vod.mp4 사용 (치지직 다운로드 결과)
    3) 둘 다 없으면 명확한 에러 메시지

source.video 형식 예:
    D:\\OBS\\녹화\\260504_방송.mp4

이렇게 두면 chzzk_download.py를 호출하지 않고도 모든 후속 스크립트가 동작합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def folder(yymmdd: str) -> Path:
    p = Path(yymmdd)
    if not p.exists():
        sys.exit(f"[X] 폴더 없음: {p.resolve()}")
    if not p.is_dir():
        sys.exit(f"[X] 폴더가 아님: {p.resolve()}")
    return p


def resolve_vod_path(work_folder: Path) -> Path:
    """현재 회차에서 사용할 영상 파일 경로를 결정."""
    src_video = work_folder / "source.video"
    if src_video.exists():
        path_str = src_video.read_text(encoding="utf-8").strip()
        if not path_str:
            sys.exit(f"[X] {src_video} 가 비어있음. 영상 파일 절대경로 한 줄 적어주세요.")
        p = Path(path_str)
        if not p.exists():
            sys.exit(f"[X] source.video에 적힌 경로가 존재하지 않음: {p}")
        if not p.is_file():
            sys.exit(f"[X] source.video는 영상 파일을 가리켜야 함 (디렉토리 X): {p}")
        return p

    vod = work_folder / "vod.mp4"
    if vod.exists():
        return vod

    sys.exit(
        f"[X] {work_folder} 에 영상이 없습니다.\n"
        f"    다음 중 하나를 준비하세요:\n"
        f"      1) {work_folder}/vod.mp4  ← 치지직 다운로드: chzzk_download.py 실행\n"
        f"      2) {work_folder}/source.video  ← OBS 녹화본 등 절대경로 한 줄"
    )


def resolve_transcript_path(work_folder: Path) -> Path:
    """후속 단계(컷·쇼츠)에서 쓸 transcript. corrected가 있으면 우선."""
    corrected = work_folder / "transcript.corrected.json"
    if corrected.exists():
        return corrected
    raw = work_folder / "transcript.json"
    if raw.exists():
        return raw
    sys.exit(f"[X] {work_folder} 에 transcript.json 이 없습니다. transcribe.py 먼저 실행하세요.")
