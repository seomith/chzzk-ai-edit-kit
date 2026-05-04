"""
correct_transcript.py — STT 결과 1차 교정

동작:
    1) glossary.json 의 replacements/slang 사전을 단순 치환 적용
    2) 신뢰도 낮은 단어(prob < THRESHOLD) 가 포함된 segment를 needs_review = true 로 마킹
    3) 결과를 transcript.corrected.json 으로 저장 (원본 transcript.json 은 유지)

이후 AI 어시스턴트(Claude Code/Codex)가 prompts/transcript_correction.md 를 따라
needs_review = true 인 segment 들의 corrected_text 를 LLM 문맥 보정으로 다듬습니다.

사용법:
    python scripts/correct_transcript.py 260504
    python scripts/correct_transcript.py 260504 --threshold 0.55
    python scripts/correct_transcript.py 260504 --force

glossary.json 위치 검색 순서:
    1) <YYMMDD>/glossary.json        (회차별 오버라이드 — 잘 안 씀)
    2) ./glossary.json                (작업 루트 = 프로젝트 공통)
    3) 키트의 examples/glossary.example.json  (없으면 빈 사전 사용 안내)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from _common import folder

LOW_CONFIDENCE_DEFAULT = 0.6  # word.prob 이 이 값 미만이면 의심


def load_glossary(work_folder: Path) -> dict:
    candidates = [
        work_folder / "glossary.json",
        Path.cwd() / "glossary.json",
    ]
    for c in candidates:
        if c.exists():
            print(f"[O] glossary 로드: {c}")
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                sys.exit(f"[X] glossary JSON 파싱 오류: {c}\n    {e}")
    print("[!] glossary.json 없음 — 사전 치환 생략, 신뢰도 마킹만 진행")
    print("    템플릿: 키트의 examples/glossary.example.json 을 작업 루트로 복사")
    return {}


def build_replacement_map(glossary: dict) -> list[tuple[re.Pattern, str]]:
    """replacements + slang을 합쳐 (정규식, 대체) 쌍의 리스트로 반환.
    긴 단어부터 매칭되도록 길이 내림차순 정렬 (부분 매칭 충돌 방지).
    """
    pairs: list[tuple[str, str]] = []
    for k, v in (glossary.get("replacements") or {}).items():
        if isinstance(k, str) and isinstance(v, str) and not k.startswith("_"):
            pairs.append((k, v))
    for k, v in (glossary.get("slang") or {}).items():
        if isinstance(k, str) and isinstance(v, str) and not k.startswith("_"):
            pairs.append((k, v))

    pairs.sort(key=lambda kv: -len(kv[0]))
    compiled = [(re.compile(re.escape(src)), dst) for src, dst in pairs]
    return compiled


def apply_replacements(text: str, repls: list[tuple[re.Pattern, str]]) -> tuple[str, int]:
    count = 0
    for pat, dst in repls:
        text, n = pat.subn(dst, text)
        count += n
    return text, count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("yymmdd")
    ap.add_argument("--threshold", type=float, default=LOW_CONFIDENCE_DEFAULT,
                    help=f"신뢰도 임계값 (기본 {LOW_CONFIDENCE_DEFAULT})")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    f = folder(args.yymmdd)
    src = f / "transcript.json"
    if not src.exists():
        sys.exit(f"[X] {src} 없음. transcribe.py 먼저 실행.")

    out = f / "transcript.corrected.json"
    if out.exists() and not args.force:
        print(f"[O] transcript.corrected.json 이미 존재 → 건너뜀 (--force 로 재실행)")
        return

    transcript = json.loads(src.read_text(encoding="utf-8"))
    glossary = load_glossary(f)
    repls = build_replacement_map(glossary)
    if repls:
        print(f"[O] 사전 치환 규칙 {len(repls)}개 로드")

    do_not_correct = set(
        x for x in (glossary.get("do_not_correct") or [])
        if isinstance(x, str) and not x.startswith("_") and not x.startswith("(")
    )

    seg_count = 0
    repl_count = 0
    needs_review = 0
    new_segments = []
    for seg in transcript.get("segments", []):
        seg_count += 1
        original = seg.get("text", "")
        corrected, n = apply_replacements(original, repls)
        repl_count += n

        # 단어 신뢰도 검사
        low_words = []
        for w in seg.get("words", []) or []:
            if w.get("prob", 1.0) < args.threshold:
                token = (w.get("word") or "").strip()
                if token and token not in do_not_correct:
                    low_words.append({
                        "word": token,
                        "start": w.get("start"),
                        "end": w.get("end"),
                        "prob": w.get("prob"),
                    })
        if low_words:
            needs_review += 1

        new_segments.append({
            **seg,
            "text_original": original,
            "corrected_text": corrected,
            "needs_review": bool(low_words),
            "low_confidence_words": low_words,
            "llm_reviewed": False,
        })

    payload = {
        "version": 1,
        "source": str(src.name),
        "glossary_used": bool(repls),
        "do_not_correct": sorted(do_not_correct),
        "threshold": args.threshold,
        "stats": {
            "segments": seg_count,
            "dictionary_replacements": repl_count,
            "segments_needing_llm_review": needs_review,
        },
        "segments": new_segments,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[O] 사전 치환 적용: {repl_count}건")
    print(f"[O] LLM 보정 필요 segment: {needs_review} / {seg_count}")
    print(f"[O] 저장: {out}")
    if needs_review > 0:
        print(f"\n[다음 단계] AI 어시스턴트에 다음과 같이 요청:")
        print(f"    \"{args.yymmdd} 자막 LLM 보정해줘\"")
        print(f"    → AI가 prompts/transcript_correction.md 따라 needs_review 항목 다듬음")


if __name__ == "__main__":
    main()
