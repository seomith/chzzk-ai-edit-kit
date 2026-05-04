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
6. 4단계(하이라이트 스크리닝)에서 후보 보고 + 내 확인 받기
7. 끝나면 260504/shorts/, 260504/longform/ 위치 알려주기

GPU 없으면 transcribe.py 모델은 medium 으로 낮춰. 진행 중 막히면 멈추고 물어봐.
```

### B. 평소 매 방송마다 (셋업 끝난 후)

```text
오늘 방송 처리해줘.
- 치지직 VOD URL: https://chzzk.naver.com/video/12345678
- 날짜(YYMMDD): 260510
```

> 이미 작업 폴더에 `AGENTS.md`가 있으면 AI가 거기 정의된 워크플로우를 그대로 따릅니다.
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
├── AGENTS.md          ← 이 키트의 AGENTS.md를 복사 (Codex/Claude Code 공용)
└── 260504/            ← 오늘 날짜 (YYMMDD)
    └── source.url     ← 치지직 VOD URL 한 줄
```

> Claude Code 환경에서 `CLAUDE.md`만 인식하는 경우: 같은 파일을 `CLAUDE.md`로 복사해도 됩니다.

`source.url` 예:
```
https://chzzk.naver.com/video/12345678
```

### Step 2. AI 어시스턴트로 폴더 열기

Claude Code/Codex 데스크톱에서 `내방송/` 폴더를 프로젝트로 추가.

### Step 3. 한 줄 명령

```
260504 방송 처리해줘
```

AI가 다음을 순서대로 실행하고, 중간중간 확인을 요청합니다:

1. VOD + 채팅 다운로드 (5~30분, 방송 길이에 따라)
2. STT 자막화 (GPU 30분 / CPU 수 시간)
3. 채팅·음량 신호 분석 (1분)
4. **하이라이트 후보 제시** ← 여기서 첫 검수
5. 자동 컷 + 쇼츠 변환 (10~30분)
6. **`shorts/`, `longform/` 폴더에서 결과 확인** ← 마지막 검수

### Step 4. 검수 → 업로드

탐색기에서 `shorts/*.mp4`를 직접 재생하며 OK/NG 판단.
NG 파일은 파일명 앞에 `_NG_` 붙여서 제외.

```
260504/shorts/
├── 01_웃긴썰.mp4          ← 업로드
├── _NG_02_애매한구간.mp4   ← 제외
└── 03_치트키.mp4          ← 업로드
```

업로드 메타데이터(제목/태그/설명)는 같은 이름의 `.txt`에 들어 있습니다.

---

## 3. 다음 회차

폴더만 새로 만들고:

```
어제 방송 처리해줘
```

또는

```
final 안 만든 폴더 다 처리해줘
```

---

## 4. 막힐 때

| 증상 | 해결 |
|---|---|
| `python: command not found` | Python 3.10+ 설치 |
| `ffmpeg: command not found` | `winget install ffmpeg` |
| 치지직 다운로드 실패 | `pip install -U yt-dlp` |
| STT가 너무 느림 | NVIDIA GPU + CUDA 설치, 또는 모델을 `medium`으로 |
| AI가 엉뚱한 구간 뽑음 | `prompts/highlight_screening.md` 본인 채널 톤에 맞게 수정 |

자세한 내용은 [`스트리머_AI편집_가이드.md`](스트리머_AI편집_가이드.md) §8 트러블슈팅.
