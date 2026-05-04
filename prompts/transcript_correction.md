# 자막 LLM 문맥 보정 프롬프트

> AI 어시스턴트가 `correct_transcript.py` 가 생성한 `transcript.corrected.json` 의
> `needs_review = true` segment 들을 문맥 보정할 때 따라야 하는 지침.
>
> 사전 치환은 이미 끝나 있습니다 (`replacements`/`slang`). 여기서는 **사전이 못 잡는
> 문맥적 오인식만** 다듬습니다.

---

## 입력

- `<YYMMDD>/transcript.corrected.json`
  - `segments[]` 각 항목:
    - `text_original` — STT 원본
    - `corrected_text` — 사전 치환 적용본 (당신이 다듬을 대상)
    - `needs_review` — true/false
    - `low_confidence_words` — `prob < threshold` 인 단어 목록
    - `llm_reviewed` — 이미 한 번 검토했는지 여부
- `glossary.json` (작업 루트)
  - `names.self`, `names.people`, `names.characters` — 인명 후보
  - `do_not_correct` — 절대 변경 금지 단어
  - `channel.main_games`, `channel.tone` — 채널 컨텍스트

---

## 출력

같은 파일(`transcript.corrected.json`)에 다음을 갱신:

- `corrected_text` — 보정된 최종 텍스트
- `llm_reviewed` — `true`
- `llm_changes` — 바꾼 게 있으면 사람이 검토할 수 있게 사유 한 줄 (없으면 생략)

원본 `text_original` 은 절대 건드리지 마세요. 비교용으로 보존합니다.

---

## 작업 절차

1. `transcript.corrected.json` 로드
2. `glossary.json` 로드 (없으면 빈 사전 가정)
3. `needs_review = true` 이면서 `llm_reviewed = false` 인 segment만 대상으로 추출
4. **세그먼트 묶음을 청크로 분할** (한 청크 약 30~50개 segment)
   - 너무 잘게 나누면 문맥이 끊어져서 보정 품질 ↓
   - 너무 크게 묶으면 토큰 한계 ↑
5. 각 청크에 대해:
   a. **앞뒤 5개 segment** 를 컨텍스트로 함께 보기 (다만 수정은 needs_review만)
   b. `low_confidence_words` 위주로 검토
   c. 문맥상 명백한 오인식만 수정 (창작 X)
   d. `do_not_correct` 단어는 절대 수정 안 함
   e. `names.*` 의 후보와 발음 유사한 단어 발견 시 우선 매칭
6. 처리한 segment의 `corrected_text` 갱신, `llm_reviewed = true` 표시
7. 변경된 항목만 사용자에게 표 형식으로 보고 (전체 X)
8. 파일 저장 후 다음 단계 안내

---

## 보정 규칙 (우선순위 순)

### 1. 인명·고유명사 우선
- `glossary.names.self/people/characters` 와 발음이 비슷한 단어가 있으면 그것으로 교체
- 예: STT가 "씨오미스" → glossary에 "seomith" 있으면 → "seomith" 로

### 2. 게임 용어 정정
- `channel.main_games` 컨텍스트에 맞춰
- 예: 롤 채널에서 "솔 킬" → "솔킬", "한 타" → "한타", "와 드" → "와드"

### 3. 줄바꿈·띄어쓰기 정상화
- 한 단어가 잘못 나뉜 경우만 합침
- 자연스러운 띄어쓰기는 유지

### 4. 명백한 동음이의어 보정
- 컨텍스트로 분명한 경우만
- 예: 게임 채널에서 "강력한 스킬" → 옳음 / "강력한 스킬을 마셨다" → "스킬을" → 의심스러우면 원본 유지

### 5. 의심스러우면 원본 유지
- 보정 confidence < 80% 면 corrected_text 유지, llm_reviewed 만 true

---

## 절대 하지 말 것

- 의미 바꾸기 (요약·축약·풀어쓰기 X)
- 문체 변경 (반말 → 존댓말 등)
- 욕설·비속어 자체 검열 (시청자 검수 단계에서 처리)
- `text_original` 수정
- `do_not_correct` 단어 변경
- `needs_review = false` 인 segment 건드리기

---

## 보고 형식 (사용자에게)

```
LLM 보정 완료: 145개 segment 검토, 38개 수정.

수정 예시 (상위 10개):
  [00:12:04]  "캐 리" → "캐리"           (게임 용어 정상화)
  [00:18:33]  "씨오미스" → "seomith"     (인명 매칭)
  [00:24:50]  "와 드" → "와드"           (게임 용어 정상화)
  ...

검토만 하고 변경 안 한 segment: 107개 (확신 부족)

저장: 260504/transcript.corrected.json
```
