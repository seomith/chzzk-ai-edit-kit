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
├── 키트경로 참조
│   └── (스크립트는 ../스트리머_편집키트/scripts/ 또는 동일 폴더)
└── YYMMDD/                    ← 방송 한 회차당 폴더 하나
    ├── source.url             ← 치지직 VOD URL (한 줄)
    ├── vod.mp4                ← 다운로드 결과
    ├── chat.json              ← 채팅 로그
    ├── transcript.json        ← STT (단어 단위 타임스탬프)
    ├── signals.json           ← 자동 신호 분석 결과
    ├── highlights.json        ← AI 스크리닝 결과 ★
    ├── clips/*.mp4            ← 자동 컷 결과 (16:9)
    ├── shorts/*.mp4 + *.txt   ← 쇼츠 (9:16) + 메타데이터
    └── longform/*.mp4         ← 롱폼 하이라이트 모음
```

날짜 형식: **YYMMDD** (예: 260504 = 2026년 5월 4일).

---

## 2. 사용자 요청 패턴 → 실행 절차

### 2-1. "YYMMDD 방송 처리해줘" / "오늘/어제 방송 처리해줘"

**전체 파이프라인 실행** (1~6단계).

```
1. python scripts/chzzk_download.py <YYMMDD>
2. python scripts/transcribe.py <YYMMDD>
3. python scripts/analyze_signals.py <YYMMDD>
4. AI 스크리닝 (아래 §3 참조) → highlights.json 생성
5. python scripts/cut_clips.py <YYMMDD>
6. python scripts/make_shorts.py <YYMMDD>
```

**각 단계마다**
- 시작 전: "이제 N단계 시작합니다. 예상 소요시간 약 X분."
- 끝난 후: 산출물 요약 (파일 개수, 크기, 특이사항)
- 4단계 후: 후보 개수와 상위 3개 제목을 출력하고 "이대로 진행할까요?" 1회 확인

### 2-2. "치지직 URL `https://...` 처리해줘"

URL에서 날짜를 추정해 폴더 생성 → `source.url` 작성 → §2-1 실행.
날짜를 못 정하면 사용자에게 폴더명(YYMMDD) 묻기.

### 2-3. "YYMMDD 하이라이트만 다시 뽑아줘"

`transcript.json`/`signals.json`이 있으면 **4단계만** 재실행.
없으면 부족한 단계부터 보충.

### 2-4. "YYMMDD 쇼츠 N개만 더 뽑아줘"

기존 `highlights.json` 읽기 → 점수 차순위 N개 추가 추출 → 5~6단계만 재실행.

### 2-5. "이번 주 방송 다 처리해줘" / "final 안 만든 폴더 다 처리해줘"

`shorts/` 폴더가 비어있는 YYMMDD 폴더를 찾아 §2-1을 순차 실행.
시작 전 "총 N개 폴더 처리합니다. 예상 시간 약 X시간." 한 번만 확인.

### 2-6. "이 클립 시작점 5초 뒤로" 같은 미세 조정

- `highlights.json`에서 해당 클립 항목의 `start` 수정
- 해당 클립만 재컷 (전체 재실행 X)

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

## 4. 검수 요청 형식

스크리닝(4단계) 직후 사용자에게 다음 형식으로 보고:

```
하이라이트 후보 N개 추출했습니다.

쇼츠 (X개):
  s01  [00:30:34 ~ 00:31:21]  방장 치트키 발동.exe       (점수 92)
  s02  [01:12:08 ~ 01:12:55]  도네 받고 박장대소           (점수 88)
  ...

롱폼 챕터 (Y개, 하이라이트 모음 Z개):
  l02  [00:30:20 ~ 01:00:00]  솔로랭크 1판 — 미친 캐리   ← 모음 포함
  ...

⚠ 검수 필요:
  - 01:15:00 부근 심한 욕설
  - 02:00:00 부근 저작권 BGM 추정 (DCMA 위험)

이대로 컷 진행할까요? (y / 수정 / 자세히)
```

`y` 확인되면 5~6단계 진행.

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
# 단일 폴더 풀 파이프라인
python scripts/chzzk_download.py 260504 \
  && python scripts/transcribe.py 260504 \
  && python scripts/analyze_signals.py 260504 \
  && python scripts/cut_clips.py 260504 \
  && python scripts/make_shorts.py 260504

# 미처리 폴더 일괄
python scripts/batch_process.py --skip-existing

# VOD 메타정보만 조회
python scripts/chzzk_download.py 260504 --info-only
```

---

## 8. 사용자에게 보고할 때

- **간결하게**: 한 줄 진행 상황 + 산출물 핵심 수치
- **시간 표기**: `1:23:45` 형식 (HH:MM:SS)
- **파일 경로**: 폴더 기준 상대 경로 (`260504/shorts/01_*.mp4`)
- 마지막에 다음 액션 1줄 ("탐색기에서 `260504/shorts/` 확인 후 NG 표시 부탁드립니다.")
