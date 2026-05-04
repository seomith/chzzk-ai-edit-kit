"""
transcribe.py — vod.mp4 → transcript.json (faster-whisper STT)

사용법:
    python scripts/transcribe.py 260504
    python scripts/transcribe.py 260504 --model medium  # 속도 우선
    python scripts/transcribe.py 260504 --device cpu    # GPU 없을 때
    python scripts/transcribe.py 260504 --force         # 재실행
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def folder(yymmdd: str) -> Path:
    p = Path(yymmdd)
    if not p.exists():
        sys.exit(f"[X] 폴더 없음: {p.resolve()}")
    return p


def detect_device() -> tuple[str, str]:
    """사용 가능한 디바이스/연산타입 자동 감지."""
    try:
        import torch  # noqa
        if torch.cuda.is_available():
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def transcribe(vod_path: Path, out_path: Path, model_size: str,
               device: str, compute_type: str, language: str = "ko") -> None:
    from faster_whisper import WhisperModel

    print(f"[.] 모델 로드: {model_size} on {device}/{compute_type}")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    print(f"[.] STT 시작: {vod_path}")
    t0 = time.time()
    segments_iter, info = model.transcribe(
        str(vod_path),
        language=language,
        vad_filter=True,
        word_timestamps=True,
        beam_size=5,
        condition_on_previous_text=False,  # 긴 영상 안정성
    )

    segments = []
    word_count = 0
    for seg in segments_iter:
        words = []
        if seg.words:
            for w in seg.words:
                words.append({
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                    "word": w.word,
                    "prob": round(getattr(w, "probability", 0.0), 3),
                })
                word_count += 1
        segments.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
        })
        if len(segments) % 50 == 0:
            print(f"    ... {len(segments)} segments / {seg.end:.0f}s 처리됨")

    elapsed = time.time() - t0

    payload = {
        "version": 1,
        "model": model_size,
        "device": device,
        "language": info.language,
        "language_prob": round(info.language_probability, 3),
        "duration": round(info.duration, 3),
        "elapsed_seconds": round(elapsed, 1),
        "segment_count": len(segments),
        "word_count": word_count,
        "segments": segments,
    }

    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[O] STT 완료: {len(segments):,} 세그먼트 / {word_count:,} 단어")
    print(f"    소요: {elapsed:.0f}s ({elapsed / max(info.duration, 1):.2f}x realtime)")
    print(f"    저장: {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--model", default="large-v3",
                    choices=["tiny", "base", "small", "medium", "large-v2", "large-v3"])
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--compute-type", default="auto",
                    help="float16, int8, int8_float16 등 (auto면 자동)")
    ap.add_argument("--language", default="ko")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    vod = f / "vod.mp4"
    if not vod.exists():
        sys.exit(f"[X] {vod} 없음. 먼저 chzzk_download.py 실행.")

    out = f / "transcript.json"
    if out.exists() and not args.force:
        print(f"[O] transcript.json 이미 존재 → 건너뜀 (--force 로 재실행)")
        return

    if args.device == "auto":
        device, compute_type = detect_device()
    else:
        device = args.device
        compute_type = "float16" if device == "cuda" else "int8"
    if args.compute_type != "auto":
        compute_type = args.compute_type

    transcribe(vod, out, args.model, device, compute_type, args.language)


if __name__ == "__main__":
    main()
