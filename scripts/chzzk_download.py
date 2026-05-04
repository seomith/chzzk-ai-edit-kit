"""
chzzk_download.py — 치지직 VOD + 채팅 로그 다운로드

사용법:
    python scripts/chzzk_download.py 260504             # YYMMDD 폴더의 source.url 사용
    python scripts/chzzk_download.py 260504 --info-only # 메타정보만 조회
    python scripts/chzzk_download.py 260504 --force     # 기존 vod.mp4 덮어쓰기

폴더 구조:
    <YYMMDD>/source.url   ← 입력 (치지직 VOD URL 한 줄)
    <YYMMDD>/vod.mp4      ← 출력
    <YYMMDD>/chat.json    ← 출력 (가능한 경우)
    <YYMMDD>/meta.json    ← 출력 (제목/방송시간/길이)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

CHZZK_VIDEO_RE = re.compile(r"chzzk\.naver\.com/video/(\d+)")
CHZZK_API_BASE = "https://api.chzzk.naver.com"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def folder(yymmdd: str) -> Path:
    p = Path(yymmdd)
    if not p.exists():
        sys.exit(f"[X] 폴더 없음: {p.resolve()}")
    return p


def read_url(yymmdd_folder: Path) -> str:
    src = yymmdd_folder / "source.url"
    if not src.exists():
        sys.exit(f"[X] {src} 가 없습니다. 치지직 VOD URL을 한 줄 적어주세요.")
    url = src.read_text(encoding="utf-8").strip()
    if not url:
        sys.exit(f"[X] {src} 가 비어있습니다.")
    return url


def extract_video_id(url: str) -> str:
    m = CHZZK_VIDEO_RE.search(url)
    if not m:
        sys.exit(f"[X] 치지직 VOD URL 형식이 아닙니다: {url}")
    return m.group(1)


def fetch_meta(video_id: str) -> dict:
    """치지직 공개 API로 VOD 메타 조회. 실패해도 치명적이지 않음."""
    try:
        r = requests.get(
            f"{CHZZK_API_BASE}/service/v3/videos/{video_id}",
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json().get("content", {})
        return {
            "video_id": video_id,
            "title": data.get("videoTitle"),
            "duration": data.get("duration"),
            "publish_date": data.get("publishDate"),
            "channel_name": (data.get("channel") or {}).get("channelName"),
            "category": data.get("videoCategoryValue"),
        }
    except Exception as e:
        print(f"[!] 메타 조회 실패 (계속 진행): {e}")
        return {"video_id": video_id}


def download_vod(url: str, out_path: Path, force: bool = False) -> None:
    if out_path.exists() and not force:
        print(f"[O] vod.mp4 이미 존재 → 건너뜀 (--force 로 덮어쓰기)")
        return

    print(f"[.] yt-dlp로 VOD 다운로드 중... (이 단계가 가장 오래 걸립니다)")
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "-o", str(out_path),
        url,
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        sys.exit("[X] yt-dlp 실패. `pip install -U yt-dlp` 후 재시도해주세요.")
    print(f"[O] 저장: {out_path}")


def fetch_chat_log(video_id: str, duration: int | None, out_path: Path, force: bool = False) -> None:
    """치지직 VOD 채팅 다시보기 API.
    엔드포인트: /service/v1/videos/{videoNo}/chats?playerMessageTime=ms&previousVideoChatNo=
    참고: 비공식적으로 알려진 엔드포인트라 변경될 수 있습니다.
    """
    if out_path.exists() and not force:
        print(f"[O] chat.json 이미 존재 → 건너뜀")
        return

    print(f"[.] 채팅 다시보기 다운로드 중...")
    headers = {"User-Agent": USER_AGENT}
    chats: list[dict] = []
    play_time_ms = 0
    step_ms = 60_000  # 1분 단위로 페이지네이션
    last_chat_no = None
    safety_loops = 0
    max_loops = 10_000

    while True:
        safety_loops += 1
        if safety_loops > max_loops:
            print("[!] 안전 루프 한도 도달 — 채팅 수집 중단")
            break

        params = {"playerMessageTime": play_time_ms}
        if last_chat_no is not None:
            params["previousVideoChatNo"] = last_chat_no

        try:
            r = requests.get(
                f"{CHZZK_API_BASE}/service/v1/videos/{video_id}/chats",
                params=params,
                headers=headers,
                timeout=10,
            )
            r.raise_for_status()
            content = r.json().get("content", {}) or {}
            page = content.get("videoChats", []) or []
        except Exception as e:
            print(f"[!] 채팅 API 오류: {e} — 수집 중단 (지금까지 {len(chats)}개)")
            break

        if not page:
            play_time_ms += step_ms
            if duration and play_time_ms > duration * 1000:
                break
            last_chat_no = None
            continue

        for c in page:
            chats.append({
                "time_ms": c.get("playerMessageTime"),
                "user": (c.get("profile") or {}).get("nickname"),
                "msg": c.get("content"),
                "type": c.get("messageTypeCode"),
            })
        last_chat_no = page[-1].get("videoChatNo")
        play_time_ms = max(play_time_ms, page[-1].get("playerMessageTime") or 0) + 1
        if duration and play_time_ms > duration * 1000:
            break

        if safety_loops % 50 == 0:
            print(f"    ... {len(chats):,}개 수집, 진행 {play_time_ms // 1000}s")
        time.sleep(0.05)  # API rate limit 보호

    out_path.write_text(
        json.dumps({"video_id": video_id, "count": len(chats), "chats": chats},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[O] 채팅 {len(chats):,}개 저장: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd", help="작업 폴더 (예: 260504)")
    ap.add_argument("--info-only", action="store_true", help="메타정보만 조회")
    ap.add_argument("--force", action="store_true", help="기존 파일 덮어쓰기")
    ap.add_argument("--no-chat", action="store_true", help="채팅 다운로드 생략")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    url = read_url(f)
    video_id = extract_video_id(url)

    meta = fetch_meta(video_id)
    (f / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    duration = meta.get("duration")
    print(f"[O] 메타: {meta.get('title') or '(제목 없음)'} / {duration}s")

    if args.info_only:
        return

    download_vod(url, f / "vod.mp4", force=args.force)

    if not args.no_chat:
        fetch_chat_log(video_id, duration, f / "chat.json", force=args.force)


if __name__ == "__main__":
    main()
