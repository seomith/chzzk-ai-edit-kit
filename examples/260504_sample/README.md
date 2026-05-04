# 260504_sample — 폴더 구조 예시

이 폴더는 **방송 한 회차가 어떤 구조로 쌓이는지** 보여주는 샘플입니다.
실제 영상 파일은 들어있지 않습니다 (구조만 참조).

```
260504/
├── source.url                   ← 사용자가 입력 (URL 한 줄)
├── meta.json                    ← 1단계 산출물 (제목/길이)
├── vod.mp4                      ← 1단계 산출물 (다운로드된 원본)
├── chat.json                    ← 1단계 산출물 (채팅 로그)
├── transcript.json              ← 2단계 산출물 (STT)
├── signals.json                 ← 3단계 산출물 (자동 신호 분석)
├── highlights.json              ← 4단계 산출물 (AI 스크리닝) ★ 검수 핵심
├── clips/
│   ├── s01_방장_치트키.mp4       ← 5단계 (16:9 원본 비율)
│   ├── s02_도네_박장대소.mp4
│   └── s03_이게_운빨.mp4
├── shorts/
│   ├── s01_방장_치트키_shorts.mp4 ← 6단계 (9:16 + 자막)
│   ├── s01_방장_치트키_shorts.txt ← 메타데이터 (제목/태그/설명)
│   ├── s02_도네_박장대소_shorts.mp4
│   └── ...
└── longform/
    ├── highlight_full.mp4        ← 5단계 (롱폼 하이라이트 모음)
    └── chapters.txt              ← 유튜브 설명란용 챕터
```

## highlights.json 예시

`highlights.example.json` 참고. 주요 필드:

- `shorts[]` — 30~60초 쇼츠 후보 (점수, 사유, 태그 포함)
- `longform_chapters[]` — 방송 전체 챕터 분할 (`include_in_highlight`로 모음 포함 여부)
- `warnings[]` — 사람이 검수해야 할 민감 구간

## 사용

본인 작업 폴더로 복사:
```bash
cp -r examples/260504_sample 내방송/260504
# source.url을 실제 치지직 VOD URL로 바꿔주세요
```

그리고 AI 어시스턴트에서:
```
260504 방송 처리해줘
```
