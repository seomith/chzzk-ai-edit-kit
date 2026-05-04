# 스트리머 방송 편집 프로젝트

이 파일은 **AI 어시스턴트(Claude Code, Codex 데스크톱 등)** 가 본 폴더에서
방송 편집 작업을 반자동으로 진행할 때 따라야 하는 워크플로우 정의입니다.

> 표준 `AGENTS.md` 형식 — Codex가 1순위로, Claude Code도 자동 인식합니다.
> Claude Code에서 `CLAUDE.md`만 읽도록 강제하는 환경이라면 이 파일을 `CLAUDE.md`로
> 이름만 바꿔 사용해도 동일하게 동작합니다.
>
> **사용자 = 스트리머**. 사용자에게 친절하게, 단계별로 진행 상황을 알리며 작업하세요.

---

## 0. 프로젝트 개요

치지직(CHZZK) 라이브 방송 VOD를 받아 → STT/신호분석으로 하이라이트 후보를 추출 →
AI(=당신)가 1차 스크리닝 → 자동 컷 → 쇼츠/롱폼 영상으로 출력.

**핵심 원칙**
1. 사람의 검수 시간을 최소화한다 (10시간 방송 → 30~60분 검수)
2. 모든 중간 산출물은 JSON으로 남긴다 (재실행/디버깅 가능)
3. 의심스러우면 사람에게 묻는다 (특히 민감 발언·욕설·저작권)

---

## 1. 폴더 구조

```
<프로젝트 루트>/
├── AGENTS.md                  ← 이 파일
├── glossary.json              ← (선택) 채널 사전 — 처음엔 비워둬도 OK
├── glossary.suggested.json    ← 자동 누적되는 후보 (사람이 가끔 검토 → glossary로 머지)
├── 키트경로 참조
│   └── (스크립트는 ../스트리머_편집키트/scripts/ 또는 동일 폴더)
└── YYMMDD/                    ← 방송 한 회차당 폴더 하나
    ├── source.url             ← 치지직 VOD URL (치지직 사용자만)
    ├── source.video           ← 외부 영상 절대경로 한 줄 (OBS 녹화본 등)
    ├── vod.mp4                ← 영상 (다운로드 결과 또는 직접 복사)
    ├── chat.json              ← 채팅 로그 (--with-chat 일 때만)
    ├── transcript.json        ← STT (단어 단위 타임스탬프)
    ├── transcript.corrected.json  ← 사전 치환 + LLM 보정본 ★ 자막용 우선
    ├── signals.json           ← 자동 신호 분석 결과
    ├── highlights.json        ← AI 스크리닝 결과 ★
    ├── clips/*.mp4            ← 자동 컷 결과 (16:9)
    ├── shorts/*.mp4 + *.txt   ← 쇼츠 (9:16) + 메타데이터
    └── longform/*.mp4         ← 롱폼 하이라이트 모음
```

날짜 형식: **YYMMDD** (예: 260504 = 2026년 5월 4일).

### 1-1. 영상 입력 방식 (둘 중 하나)

| 케이스 | 무엇을 둘까 | 동작 |
|---|---|---|
| 치지직 VOD 받기 | `source.url` (URL 한 줄) | `chzzk_download.py` 가 `vod.mp4` 생성 |
| OBS 등 외부 녹화본 사용 | `source.video` (영상 절대경로 한 줄) **또는** `vod.mp4` 직접 복사 | 다운로드 단계 자동 스킵 |

`_common.resolve_vod_path()` 가 `source.video → vod.mp4` 순으로 해석합니다.
**자동 감지 안 함** — 사용자/AI 가 어느 영상을 쓸지 명시적으로 알려주세요.

### 1-2. 채팅 로그는 옵션

기본은 채팅 다운로드 OFF. 다음 경우만 권장:
- 도네 리액션·시청자 소통 위주
- 호러·깜짝 콘텐츠 (시청자 반응이 중요한 신호)

활성화: `chzzk_download.py --with-chat` 또는 사용자가 "채팅도 받아줘" 라고 말함.
채팅 없으면 `analyze_signals.py` 가 음량·발화 가중치를 자동으로 상향 조정합니다.

---

## 2. 사용자 요청 패턴 → 실행 절차

### 2-1. "YYMMDD 방송 처리해줘" / "오늘/어제 방송 처리해줘"

**전체 파이프라인 실행**.

```
1.  python scripts/chzzk_download.py <YYMMDD>     # source.url 있을 때만
2.  python scripts/transcribe.py <YYMMDD>          # 모델 자동 선택 (§A)
2.5 python scripts/correct_transcript.py <YYMMDD>  # 사전 치환 + 신뢰도 마킹
2.6 (선택) AI 자막 LLM 보정 — prompts/transcript_correction.md 사용
3.  python scripts/analyze_signals.py <YYMMDD>
4.  AI 스크리닝 (§3 참조) → highlights.json 생성
5.  python scripts/cut_clips.py <YYMMDD>
6.  python scripts/make_shorts.py <YYMMDD>
```

**각 단계마다**
- 시작 전: "이제 N단계 시작합니다. 예상 소요시간 약 X분."
- 끝난 후: 산출물 요약 1줄 (파일 개수, 크기, 특이사항)
- 2.5 후: `transcript.corrected.json` 의 `segments_needing_llm_review` 수치와
  추정 소요시간(약 segments × 2초)을 1줄로 보고하고 **묻지 말고 2.6 자동 진행**
  (사용자가 명시적으로 "LLM 보정 건너뛰어" 라고 한 경우에만 스킵).
  같은 단계에서 `glossary.suggested.json` 누적 결과도 1줄 보고
  (예: `glossary 후보 신규 4 / 누적 26개`). 누적 ≥ 10 이면 한 줄 더:
  `검토 권장 — "글로써리 후보 검토해줘"`
- 4단계 후: 후보 개수와 상위 3개 제목을 1줄로 보고만 하고 **묻지 말고 5단계로 진행**
  (사용자가 명시적으로 "스크리닝 결과 먼저 보여줘" 라고 한 경우에만 멈춤)

**정지 0회 — 논스톱 진행이 기본.** 사용자가 명시적으로 검수를 요청하지 않는 한
첫 명령부터 6단계 결과까지 끊지 않고 끝까지 진행합니다.

**5단계 한도 (자원 절약 정책)**
- 쇼츠는 점수 내림차순 **상위 5개만** mp4 컷 (`cut_clips.py --shorts-limit 5`, 기본값)
- 롱폼은 `include_in_highlight = true` 챕터를 합친 `highlight_full.mp4` 1개
- 컷되지 않은 쇼츠 후보 / 모든 챕터 / `warnings` 는 `<YYMMDD>/summary.md` 에 목록만
- 사용자가 "쇼츠 10개 만들어줘" 같이 명시하면 그 값으로 `--shorts-limit` 갱신

### 2-2. "치지직 URL `https://...` 처리해줘"

URL에서 날짜를 추정해 폴더 생성 → `source.url` 작성 → §2-1 실행.
날짜를 못 정하면 사용자에게 폴더명(YYMMDD) 묻기.

### 2-3. "YYMMDD 하이라이트만 다시 뽑아줘"

`transcript.json`/`signals.json`이 있으면 **4단계만** 재실행.
없으면 부족한 단계부터 보충.

### 2-4. "YYMMDD 쇼츠 N개만 더 뽑아줘"

기존 `highlights.json` 읽기 → 점수 차순위 N개 추가 추출 → 5~6단계만 재실행.

### 2-5. "이번 주 방송 다 처리해줘" / "shorts 안 만든 폴더 다 처리해줘"

`shorts/` 폴더가 비어있는 YYMMDD 폴더를 찾아 §2-1을 순차 실행.
시작 전 "총 N개 폴더 처리합니다. 예상 시간 약 X시간." 한 번만 확인.

OBS 녹화본 폴더를 지정받은 경우에는 해당 폴더에서 `mp4/mkv/mov` 파일명을 훑어
`YYMMDD` 날짜를 찾고, 작업 루트에 `<YYMMDD>/source.video` 를 만든 뒤 같은 절차로 처리합니다.
배치 스크립트 기준:

```
python scripts/batch_process.py --root D:\OBS\녹화 --work-root .
```

`--root` 는 OBS 녹화본이 저장된 입력 폴더, `--work-root` 는 `YYMMDD/` 작업 폴더를 만들 위치입니다.
`--work-root` 를 생략하면 기존 `YYMMDD/` 폴더가 있는 root는 그대로 작업 루트로 쓰고,
OBS 영상 파일만 있는 root는 현재 폴더에 작업 폴더를 만듭니다.

### 2-6. "이 클립 시작점 5초 뒤로" 같은 미세 조정

- `highlights.json`에서 해당 클립 항목의 `start` 수정
- 해당 클립만 재컷 (전체 재실행 X)

### 2-7. "YYMMDD 자막 LLM 보정해줘" / "오타 교정해줘"

`transcript.corrected.json` 의 `needs_review = true` 이고 `llm_reviewed = false`
인 segment 만 보정. 자세한 절차·금지사항은 `prompts/transcript_correction.md`.

- 사전 치환만 자동 (`correct_transcript.py`), LLM 보정은 본 패턴이나 §2-1 의 2.6 단계에서만
- 보정 후 변경된 항목만 표 형식으로 사용자에게 보고
- 원본 `text_original` 절대 수정 X

### 2-8. "이 영상 써줘 D:\OBS\xxx.mp4" / "OBS 녹화본으로 처리"

- `<YYMMDD>/source.video` 에 절대경로 한 줄 기록
- 또는 사용자가 직접 `vod.mp4` 로 복사한 경우 그대로 사용
- §2-1 의 1번 다운로드 단계는 자동 스킵 (`source.url` 없으면)

### 2-11. "OOO 이 뭐야?" / "OOO 설명해줘" — 용어 질문

스트리머는 비개발자입니다. 모르는 단어가 자주 등장해요 (`STT`, `EDL`, `ass`, `VAD`,
`needs_review`, `source.video` 등).

이런 질문을 받으면:

1. **`용어집.md` 를 먼저 검색** — 키트 전체 용어가 한국어로 정리돼 있음
2. 있으면: 한 줄 정의 + (필요하면) 우리 키트에서 어떻게 쓰이는지 한 줄
3. 없으면: 일반 지식으로 답하되 키트 컨텍스트와 연결
4. **무조건 짧게**. 일상 어휘. 강의하지 말 것.

예시:
> 사용자: "STT가 뭐야?"
> AI: "Speech-to-Text — 말소리를 글자로 받아쓰는 것. 우리 키트에선 `faster-whisper`
> 가 그 역할이고 결과는 `transcript.json` 에 저장돼요."

### 2-10. "글로써리 후보 검토해줘" / "glossary 후보 봐줘"

`./glossary.suggested.json` 에 누적된 후보들을 사람과 한 개씩 컨펌해서
정식 `glossary.json` 으로 옮기는 절차. 자세한 워크플로우는 **`prompts/glossary_review.md`**.

핵심 원칙:
- **자동 머지 절대 금지** (잘못된 STT가 사전이 되어 굳어지는 피드백 루프 방지)
- 사용자 확인 없이는 `glossary.json` 한 줄도 바꾸지 말 것
- 한 라운드에 20개씩만 처리, 사용자가 `q` 하면 그 시점까지 저장하고 종료
- `_ignored` 키 (영구 거절 목록) 도 같이 관리

이 단계는 §2-1 의 자동 파이프라인에 **포함되지 않음** (사용자 명시 시에만 진입).

### 2-9. "<영상 파일> 편집본 만들어줘" — 가장 짧은 한 줄 명령

가장 친화적인 트리거. 사용자가 영상 파일 하나만 던지고 끝까지 자동.

예시:
- `"260504_방송.mp4 편집본 만들어줘"`
- `"D:\OBS\녹화\260510_롤.mp4 편집본 만들어줘"`
- `"./영상/오늘방송.mp4 편집본 부탁"`

**AI 가 따라야 하는 절차**:
1. 입력 토큰을 영상 경로로 해석 (절대/상대/파일명만 모두 허용)
   - 절대경로 / 상대경로면 `Path(...).resolve()`
   - 파일명만이면 현재 폴더 → 사용자 OBS 기본 폴더 순으로 검색, 못 찾으면 사용자에게 묻기
   - 파일이 존재 + mp4/mkv/mov 인지 확인
2. 폴더명(YYMMDD) 결정
   - 파일명에서 `\d{6}` 패턴 검색 → 첫 매치를 YYMMDD 후보로
   - 후보가 합리적 범위(오늘 ± 90일)면 채택
   - 없거나 합리적이지 않으면 **오늘 날짜를 YYMMDD 형식으로** 자동 사용
3. `<YYMMDD>/` 폴더 생성 (이미 존재하면 그대로 사용)
4. `<YYMMDD>/source.video` 에 영상 절대경로 한 줄 기록
5. §2-1 절차 진행 — 1번 다운로드는 자동 스킵, 2단계부터 시작
6. 끝나면 `<YYMMDD>/summary.md` 위치만 한 줄로 안내하고 마무리

**확인은 시작 직전 1회만**:
```
[i] 영상: D:\OBS\녹화\260510_롤.mp4
[i] 작업 폴더: 260510/
[i] STT 모델: large-v3 (CUDA, VRAM 16.0GB)
[i] 예상 소요시간: 약 1시간 30분
시작합니다…
```

---

## 3. AI 하이라이트 스크리닝 (4단계, AI=당신의 역할)

### 입력
- `<YYMMDD>/transcript.json` — STT 전체 텍스트 + 타임스탬프
- `<YYMMDD>/signals.json` — 자동 추출된 후보 구간 (채팅 폭발/음량 피크 등)
- `prompts/highlight_screening.md` — 스크리닝 지침

### 출력 (`<YYMMDD>/highlights.json`)

```json
{
  "version": 1,
  "vod_seconds": 14820,
  "shorts": [
    {
      "id": "s01",
      "start": 1834.5,
      "end": 1881.2,
      "title": "방장 치트키 발동.exe",
      "tags": ["롤", "한타", "역전"],
      "reason": "채팅 ㅋㅋ 폭발 + 음량 피크 동시 / 펀치라인 명확",
      "score": 92
    }
  ],
  "longform_chapters": [
    {
      "id": "l01",
      "start": 0,
      "end": 1820,
      "title": "오프닝 / 오늘 패치 잡담",
      "include_in_highlight": false
    },
    {
      "id": "l02",
      "start": 1820,
      "end": 3600,
      "title": "솔로랭크 1판 — 미친 캐리",
      "include_in_highlight": true
    }
  ],
  "warnings": [
    {"start": 4500, "end": 4530, "type": "explicit_language", "note": "심한 욕설 구간"},
    {"start": 7200, "end": 7245, "type": "copyrighted_bgm", "note": "저작권 BGM 추정"}
  ]
}
```

### 작업 시 주의
- **시작/끝은 5초 여유**를 두되, 펀치라인 직후 1초 안에 끝낼 것
- 쇼츠 후보는 **30~60초**가 가장 좋음 (15초 미만, 90초 초과는 점수 -10)
- 광고·잡담·로딩 화면은 절대 후보에 넣지 말 것
- 동일 구간이 쇼츠와 롱폼 모두에 들어가도 OK (다른 길이로 활용)
- `warnings`는 검수에서 사람이 마지막으로 확인할 항목

---

## 4. 4단계 직후 보고 형식 (정지 X — 보고만 하고 진행)

스크리닝 결과를 1줄 + 표 형태로 보고하고, **묻지 말고** 5~6단계 자동 진행.
검수가 필요하면 사용자가 결과(`shorts/*.mp4`, `summary.md`) 보고 말함.

```
[O] 하이라이트 N개 추출 (쇼츠 X / 롱폼 챕터 Y / warnings W). 5단계로 진행합니다.

상위 후보 (점수순):
  s01  92  [00:30:34~00:31:21]  방장 치트키 발동.exe
  s02  88  [01:12:08~01:12:55]  도네 받고 박장대소
  s03  81  [01:45:02~01:45:48]  이게 운빨? 실력?
  ...
```

이후 자동으로 `cut_clips.py` (상위 5개 + 롱폼 1개 + summary.md) → `make_shorts.py`
실행. 모든 결과는 마지막에 `<YYMMDD>/summary.md` 한 파일로 정리되어 사용자가
탐색기에서 더블클릭만 해도 읽을 수 있음.

**예외 — 다음 경우는 멈춰서 확인**
- 영상 길이가 비정상 (10분 미만 / 20시간 초과)
- 후보가 0개 (신호 임계값 너무 높거나 STT 실패)
- ffmpeg / 디스크 / 인증 등 시스템 에러
- 사용자가 명령에서 "스크리닝 결과 먼저 보여줘" 같이 명시

---

## 5. 재시작 / 캐시 / 멱등성

각 스크립트는 결과 파일이 이미 있으면 **건너뛰는 것이 기본**입니다.
강제 재실행을 원하면 사용자가 명시: "STT 다시 돌려줘" → `--force` 플래그 사용.

```
python scripts/transcribe.py 260504 --force
```

---

## 6. 에러 처리

- 다운로드 실패 → URL 재확인 요청, yt-dlp 업데이트 안내
- STT 메모리 부족 → 모델 단계 낮추기 제안 (`large-v3` → `medium`)
- AI 스크리닝 결과가 비어있음 → 신호 임계값을 낮춰 재실행 제안
- ffmpeg 에러 → 입력 파일 무결성 (`ffprobe`) 확인 후 보고

**절대 하지 말 것**
- 사용자 확인 없이 원본 `vod.mp4` 삭제
- `highlights.json` 사용자 수정본 덮어쓰기 (백업 후 작업)
- `--no-verify` 같은 강제 옵션 사용

---

## 7. 자주 사용하는 명령

```bash
# 단일 폴더 풀 파이프라인 (치지직)
python scripts/chzzk_download.py 260504 \
  && python scripts/transcribe.py 260504 \
  && python scripts/correct_transcript.py 260504 \
  && python scripts/analyze_signals.py 260504 \
  && python scripts/cut_clips.py 260504 \
  && python scripts/make_shorts.py 260504

# OBS 녹화본 사용 (다운로드 단계 없음)
# 사전: 260504/source.video 에 영상 절대경로 한 줄
python scripts/transcribe.py 260504 \
  && python scripts/correct_transcript.py 260504 \
  && python scripts/analyze_signals.py 260504 \
  && python scripts/cut_clips.py 260504 \
  && python scripts/make_shorts.py 260504

# 미처리 폴더 일괄 (OBS 녹화 폴더를 입력으로 사용)
python scripts/batch_process.py --root D:\OBS\녹화 --work-root .

# 채팅도 받기 (도네 리액션 채널 등)
python scripts/chzzk_download.py 260504 --with-chat

# VOD 메타정보만 조회
python scripts/chzzk_download.py 260504 --info-only

# 쇼츠 한도 조절 (기본 5)
python scripts/cut_clips.py 260504 --shorts-limit 10  # 상위 10개
python scripts/cut_clips.py 260504 --shorts-limit 0   # 제한 없음
```

---

## 8. 사용자에게 보고할 때

- **간결하게**: 한 줄 진행 상황 + 산출물 핵심 수치
- **시간 표기**: `1:23:45` 형식 (HH:MM:SS)
- **파일 경로**: 폴더 기준 상대 경로 (`260504/shorts/01_*.mp4`)
- 마지막에 다음 액션 1줄 ("탐색기에서 `260504/shorts/` 확인 후 NG 표시 부탁드립니다.")

---

## A. 부록 — STT 모델·디바이스 자동 분기

`transcribe.py` 는 사용자가 `--model`/`--device` 를 명시하지 않으면 다음 규칙으로 자동 선택:

| 환경 | 자동 선택 모델 | 비고 |
|---|---|---|
| GPU + VRAM ≥ 9GB | `large-v3` | 5080/4090/3090 등 |
| GPU + VRAM ≥ 5GB | `medium` | 4060/3060 8GB 등 |
| GPU + VRAM <  5GB | `small` | 저사양 GPU |
| CPU only | `small` | 한국어 실용 최소선 |

사용자가 명시한 `--model` 은 항상 자동 선택보다 우선합니다.

CPU 사용자에게 `large-v3` 강요는 비현실적(10시간 방송 → 10~20시간). `small` 도 의미
파악·하이라이트 스크리닝에는 충분하지만, 자막 burn-in 품질을 끌어올리려면
`correct_transcript.py` 의 사전 치환 + LLM 보정 단계로 보완하세요.

## B. 부록 — 자막 LLM 보정 정책

§2-1 의 2.6 단계는 **항상 자동 진행** 합니다 (확인 묻지 않음).

- 시작 전 한 줄로 보고: `[i] LLM 보정 시작 — needs_review N개, 약 X분 예상`
- 사용자가 "LLM 보정 건너뛰어" / "교정 스킵" 같이 명시한 경우에만 생략
- needs_review 가 매우 많아 시간이 길어질 것 같으면 보고에 그 수치를 그대로 노출
  (사용자가 진행 도중에 중단하고 싶으면 직접 끊을 수 있게)
