# 스트리머 AI 편집 키트 — 5분 빠른 시작

치지직 VOD 한 개를 **AI 반자동**으로 쇼츠/롱폼까지 만들어보는 가장 빠른 절차.
자세한 설명은 [`스트리머_AI편집_가이드.md`](스트리머_AI편집_가이드.md) 참고.

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
