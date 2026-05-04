# 스트리머 AI 편집 키트 — 5분 빠른 시작

치지직 VOD 한 개를 **AI 반자동**으로 쇼츠/롱폼까지 만들어보는 가장 빠른 절차.
자세한 설명은 [`스트리머_AI편집_가이드.md`](스트리머_AI편집_가이드.md) 참고.

---

## 0. AI에게 이 한 덩어리 던지기 (가장 빠른 길)

**Claude Code 또는 Codex 데스크톱**을 열고 작업할 새 폴더(예: `내방송/`)를 프로젝트로 추가한 뒤,
아래 두 프롬프트 중 본인 상황에 맞는 것을 그대로 복사해서 붙여넣으세요.
**`URL`과 `날짜(YYMMDD)` 두 줄만 본인 것으로 바꾸면** AI가 알아서 끝냅니다.

### A. 첫 셋업 + 첫 영상 처리 (최초 1회)

```text
다음 GitHub 레포의 키트를 사용해서 내 치지직 방송을 쇼츠/롱폼으로 만들어줘.

키트: https://github.com/seomith/chzzk-ai-edit-kit
치지직 VOD URL: https://chzzk.naver.com/video/00000000
방송 날짜: 260504

진행 절차:
1. 키트 레포를 ./chzzk-ai-edit-kit 으로 git clone
2. 그 폴더 안의 install.bat 실행해서 의존성 설치 (실패하면 README.md 참고해서 수동 설치)
3. 키트의 AGENTS.md 를 현재 폴더(작업 루트)에 복사
4. 260504/ 폴더 만들고 source.url 파일에 위 VOD URL 한 줄 적기
5. AGENTS.md 의 "260504 방송 처리해줘" 절차대로 1~6단계 진행
6. 4단계(하이라이트 스크리닝)에서 후보 보고만 하고 멈추지 말고 계속 진행
7. 끝나면 260504/shorts/, 260504/longform/ 위치 알려주기

GPU 없으면 transcribe.py 모델은 small 로 낮춰. 시스템 에러가 아니면 중간에 묻지 말고 끝까지 진행.
```

### B. 평소 매 방송마다 (셋업 끝난 후)

가장 짧은 형태 — 영상 파일 한 줄:

```text
D:\OBS\녹화\260510_방송.mp4 편집본 만들어줘
```

또는 치지직 사용자:

```text
오늘 방송 처리해줘.
- 치지직 VOD URL: https://chzzk.naver.com/video/12345678
- 날짜(YYMMDD): 260510
```

> 이미 작업 폴더에 `AGENTS.md`가 있으면 AI가 거기 정의된 워크플로우를 그대로 따라
> **정지 0회 논스톱**으로 끝까지 진행합니다 (쇼츠 상위 5개 + 롱폼 1개 + summary.md).
> "어제 방송 처리해줘", "이번 주 미처리 폴더 다 돌려줘" 같은 자연어도 동일하게 이해합니다.

---

## 1. 설치 (한 번만)

```bash
# 1) 이 키트 폴더에서
install.bat
```

자동 체크/설치되는 것:
- Python 가상환경 (`venv/`)
- `yt-dlp`, `faster-whisper`, `auto-editor`, `ffmpeg-python` 등
- ffmpeg 존재 확인 (없으면 안내)

**AI 어시스턴트** (둘 중 하나)
- [Claude Code](https://claude.ai/code) 설치, 또는
- [Codex 데스크톱](https://openai.com) 설치

---

## 2. 첫 영상 만들기

### Step 1. 작업 폴더 만들기

```
내방송/
├── AGENTS.md           ← 이 키트의 AGENTS.md를 복사 (Codex/Claude Code 공용)
├── glossary.json       ← (선택) 처음엔 비워둬도 OK — 자동 누적되니까
├── glossary.suggested.json  ← 자동 누적 후보 (가끔 "글로써리 후보 검토해줘" 한 줄로 머지)
└── 260504/             ← 오늘 날짜 (YYMMDD)
    ├── source.url      ← 치지직 사용자: VOD URL 한 줄
    └── source.video    ← OBS 사용자: 영상 절대경로 한 줄 (둘 중 하나만 두면 됨)
```

> Claude Code 환경에서 `CLAUDE.md`만 인식하는 경우: 같은 파일을 `CLAUDE.md`로 복사해도 됩니다.

`source.url` 예:
```
https://chzzk.naver.com/video/12345678
```

`source.video` 예 (OBS 녹화본 경로):
```
D:\OBS\녹화\260504_방송.mp4
```

### Step 2. AI 어시스턴트로 폴더 열기

Claude Code/Codex 데스크톱에서 `내방송/` 폴더를 프로젝트로 추가.

### Step 3. 한 줄 명령 (가장 짧은 형태)

영상 파일만 던지면 됩니다. AI가 폴더 만들고 끝까지 알아서:

```
260504_방송.mp4 편집본 만들어줘
```

또는 절대경로로:

```
D:\OBS\녹화\260504_방송.mp4 편집본 만들어줘
```

치지직에서 받을 거면:

```
260504 방송 처리해줘    (또는)    https://chzzk.naver.com/video/12345678 처리해줘
```

AI가 **정지 0회로** 끝까지 자동 진행합니다:

1. (치지직만) VOD 다운로드 — 5~30분
2. STT — 모델 자동 선택 (RTX 5080급 = 30분~1시간 / CPU = 1~2시간)
3. 사전 치환 + LLM 자막 보정 — 5~15분
4. 신호 분석 + AI 하이라이트 스크리닝 — 5분
5. 자동 컷 (점수 상위 5개 쇼츠 + 롱폼 1개) + 쇼츠 변환 — 10~20분
6. `<YYMMDD>/summary.md` 에 모든 결과 정리 (만든 것 / 안 만든 후보 / ⚠ 검수 필요)

> 자막은 영상에 박지 않고 **`.srt` 사이드 파일**로 같이 떨어집니다 (`s01_*.mp4` + `s01_*.srt`).
> 유튜브 자막 업로드, 프리미어/다빈치 import 가능. 영상에 박으려면 `--burn-subs`.

### Step 4. summary.md 한 번 → 검수 → 업로드

먼저 `<YYMMDD>/summary.md` 를 더블클릭해서 한 번 쭉 읽기 — 만든 쇼츠 5개,
미생성 후보 N개, ⚠ 검수 필요 항목까지 한 페이지에 다 있습니다.

그다음 탐색기에서 `shorts/*.mp4` 5개를 재생하며 OK/NG 판단.
NG 파일은 파일명 앞에 `_NG_` 붙여서 제외:

```
260504/shorts/
├── s01_방장_치트키.mp4         ← 업로드
├── _NG_s02_애매한구간.mp4       ← 제외
└── s03_도네_박장대소.mp4        ← 업로드
```

업로드 메타데이터(제목/태그/설명)는 같은 이름의 `.txt`에 들어 있습니다.

**더 만들고 싶으면** AI에 한 줄: `"260504 쇼츠 5개 더 만들어줘"`

---

## 3. 다음 회차

폴더만 새로 만들고:

```
어제 방송 처리해줘
```

또는

```
shorts 안 만든 폴더 다 처리해줘
```

OBS 녹화본이 한 폴더에 쌓이는 방식이면 녹화 파일명에 `260510` 같은 YYMMDD 날짜가 들어가게 두고:

```bash
python scripts/batch_process.py --root D:\OBS\녹화 --work-root .
```

`--root` 는 OBS 녹화본 폴더, `--work-root` 는 `260510/` 같은 작업 폴더를 만들 위치입니다.

---

## 4. 막힐 때

| 증상 | 해결 |
|---|---|
| `python: command not found` | Python 3.10+ 설치 |
| `ffmpeg: command not found` | `winget install ffmpeg` |
| 치지직 다운로드 실패 | `pip install -U yt-dlp` |
| STT가 너무 느림 | `transcribe.py`가 디바이스/VRAM 자동 감지 — `--model small` 명시도 가능 |
| 자막에 인명·신조어 오타 | 키트가 `glossary.suggested.json`에 자동 누적 → "글로써리 후보 검토해줘" 로 정식 사전 머지 |
| OBS 녹화본 쓰고 싶음 | `<YYMMDD>/source.video`에 영상 절대경로 한 줄 |
| AI가 엉뚱한 구간 뽑음 | `prompts/highlight_screening.md` 본인 채널 톤에 맞게 수정 |

자세한 내용은 [`스트리머_AI편집_가이드.md`](스트리머_AI편집_가이드.md) §8 트러블슈팅.

> **모르는 단어 만나면**: AI 에 `"OOO 이 뭐야?"` 한 줄 → [`용어집.md`](용어집.md) 자동 참조해서 한국어로 짧게 답해줍니다.
