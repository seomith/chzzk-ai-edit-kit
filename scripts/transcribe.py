"""
transcribe.py — vod.mp4 → transcript.json (faster-whisper STT)

사용법:
    python scripts/transcribe.py 260504                  # 디바이스/VRAM 자동 분기
    python scripts/transcribe.py 260504 --model medium   # 모델 명시
    python scripts/transcribe.py 260504 --device cpu     # 디바이스 명시
    python scripts/transcribe.py 260504 --force          # 재실행

영상 파일은 _common.resolve_vod_path 가 결정 (source.video 우선, 없으면 vod.mp4).

자동 모델 선택 규칙:
    GPU + VRAM ≥ 9GB → large-v3
    GPU + VRAM ≥ 5GB → medium
    GPU + VRAM <  5GB → small
    CPU only          → small
사용자가 --model 로 명시하면 그 값이 항상 우선합니다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from _common import folder, resolve_vod_path


def detect_device_and_model() -> tuple[str, str, str, str]:
    """
    반환: (device, compute_type, recommended_model, info_line)
    """
    try:
        import torch
        if torch.cuda.is_available():
            try:
                props = torch.cuda.get_device_properties(0)
                vram_gb = props.total_memory / (1024 ** 3)
                name = props.name
            except Exception:
                vram_gb = 0
                name = "Unknown CUDA"
            if vram_gb >= 9:
                model = "large-v3"
            elif vram_gb >= 5:
                model = "medium"
            else:
                model = "small"
            return ("cuda", "float16", model,
                    f"CUDA 감지: {name}, VRAM {vram_gb:.1f}GB → 권장 모델 {model}")
    except Exception:
        pass
    return ("cpu", "int8", "small",
            "GPU 미감지 → CPU 모드, 권장 모델 small")


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
    ap.add_argument("--model", default="auto",
                    help="auto(기본), tiny, base, small, medium, large-v2, large-v3")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--compute-type", default="auto",
                    help="float16, int8, int8_float16 등 (auto면 자동)")
    ap.add_argument("--language", default="ko")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    vod = resolve_vod_path(f)

    out = f / "transcript.json"
    if out.exists() and not args.force:
        print(f"[O] transcript.json 이미 존재 → 건너뜀 (--force 로 재실행)")
        return

    auto_device, auto_compute, auto_model, info_line = detect_device_and_model()
    print(f"[O] {info_line}")

    device = auto_device if args.device == "auto" else args.device
    if args.compute_type != "auto":
        compute_type = args.compute_type
    else:
        compute_type = auto_compute if device == auto_device else (
            "float16" if device == "cuda" else "int8"
        )
    model_size = auto_model if args.model == "auto" else args.model

    if args.model == "auto":
        print(f"[O] 자동 선택된 모델: {model_size}")
    else:
        print(f"[O] 사용자 지정 모델: {model_size}")

    transcribe(vod, out, model_size, device, compute_type, args.language)


if __name__ == "__main__":
    main()
