# 글로써리 후보 검토 절차

> 사용자가 **"글로써리 후보 검토해줘"** / **"glossary 후보 봐줘"** 같은 명령을 했을 때
> AI 어시스턴트가 따라야 하는 워크플로우.
>
> 목적: `glossary.suggested.json` 에 누적된 후보들을 사람과 함께 한 개씩 컨펌해서
> 정식 `glossary.json` 으로 옮긴다. **자동 머지는 절대 하지 말 것** (피드백 루프 위험).

---

## 입력
- 작업 루트의 `glossary.suggested.json`
- 작업 루트의 `glossary.json` (없으면 키트의 `examples/glossary.example.json` 을
  복사해서 새로 만들기 — 빈 사전 OK)

## 출력
- 사용자가 OK 한 후보는 `glossary.json` 의 적절한 섹션에 추가
- 처리(추가 또는 거절)된 후보는 `glossary.suggested.json` 에서 제거
- 끝나면 통계 보고

---

## 작업 절차

### 1. 후보 정렬

`glossary.suggested.json` 을 로드하고 `candidates` 를 다음 우선순위로 정렬:

1. `count` 내림차순 (자주 등장한 것부터)
2. `source == "llm"` 우선 (LLM이 정정 후보까지 매겨둔 것)
3. `last_seen` 내림차순 (최근 자주 보인 것 우선)

상위 20개만 한 라운드에서 처리 (한 번에 너무 많으면 사용자 피로).

### 2. 한 개씩 사용자에게 제시

후보 한 개당 다음 형식으로:

```
[1/20]  "씨오미스"  (12회, source: llm)
        suggested → "seomith"
        예: "...오늘은 씨오미스가 1픽 했네..."
            "...씨오미스 한 판 더 가자..."
            "...씨오미스 멘탈 나갔다..."

  → 정식 사전에 추가할까요?
     y) 추가 (suggested 그대로)
     e) 추가하되 정정 단어를 다르게 입력 (사용자 입력 받기)
     d) do_not_correct 에 등록 (인명·고유명사라 보호)
     n) 거절 (이번에만 — 다음 누적에서 다시 후보로 올라옴)
     k) 영구 거절 (다시 후보로 올리지 말 것 — _ignored 목록에 등록)
     s) 스킵 (지금 결정 안 함 — suggested 에 그대로 둠)
     q) 그만 (지금까지 처리한 것만 저장하고 종료)
```

사용자가 한 글자씩 답하면 다음 후보로 넘어감. 여러 개를 한 번에 답해도 OK
(예: "y y d n s y").

### 3. 분류 — 어디 섹션에 넣을지

| 사용자 응답 | glossary.json 의 어디로 |
|---|---|
| `y` (suggested 그대로) | `suggested_correction` 이 있으면 `replacements`, 없으면 `names.people` |
| `e` (사용자 정정 입력) | 입력값 형태에 따라 `replacements` 또는 `names.people` |
| `d` (보호) | `do_not_correct` 배열에 추가 |
| `n` (거절) | suggested 에서 제거 (또는 그대로 두기 — 다음 회차 때 다시 등장) |
| `k` (영구 거절) | suggested 에서 제거 + `_ignored` 키에 추가 (다음 회차 때 다시 안 올림) |
| `s` (스킵) | suggested 에 그대로 |
| `q` (그만) | 지금까지 변경 저장하고 종료 |

`_ignored` 는 suggested 파일의 메타 키:

```json
{
  "version": 1,
  "candidates": { ... },
  "ignored": ["가나다", "라마바", ...]
}
```

`correct_transcript.py` 의 `update_suggestions()` 가 이 키를 읽어서
`ignored` 에 있는 단어는 candidates 로 다시 올리지 말 것.

### 4. 분류 결정 보조 규칙

`y` 응답 시 어디 섹션에 넣을지 자동 판단:

- `suggested_correction` 이 있고 영문/숫자 포함 → `replacements`
  (예: `"씨오미스" → "seomith"`)
- `suggested_correction` 이 한국어이고 글자 수 비슷 → `replacements`
  (예: `"발로 란트" → "발로란트"`)
- `suggested_correction` 이 없고 `source == "stt"` → 사용자에게 한 번 더 묻기
  ("이 단어가 뭔가요? a) 인명/닉 b) 게임용어 c) 신조어 d) 그 외")
- 한국어 자모만 (ㄱㄴㄷ ...) → `slang` (예: `"ㅇㅈ" → "인정"`)

### 5. 저장

처리 완료 후:
- `glossary.json` 에 추가된 항목들 일괄 반영 (들여쓰기 유지, 기존 주석/구조 보존)
- `glossary.suggested.json` 에서 처리된 후보 키 삭제
- 양쪽 파일 모두 저장

### 6. 보고

```
글로써리 후보 검토 완료.

처리: 20개
  - 정식 사전 추가: 12개
    · replacements: 8개  (씨오미스→seomith, 발로란트, ...)
    · names.people: 3개  (롤군, 한선수, ...)
    · slang: 1개         (ㄱㅈ → 가즈아)
  - 보호 등록 (do_not_correct): 2개
  - 영구 거절: 3개
  - 스킵: 3개

남은 후보: 7개 (./glossary.suggested.json)
다음 회차부터 자동으로 적용됩니다.
```

---

## 주의

- **glossary.json 의 기존 주석(`_comment_*` 키)·구조는 절대 손상 X**
- 같은 키가 이미 정식 사전에 있으면 덮어쓰지 말고 사용자에게 물어보기
- 한 번에 너무 많이 처리하면 사용자가 지침 → 20개씩 끊고 더 할지 묻기
- 사용자가 도중에 `q` (그만) 하면 지금까지 결정한 것만 저장하고 깔끔하게 종료
