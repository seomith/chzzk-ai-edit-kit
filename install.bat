@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo =====================================================
echo   스트리머 AI 편집 키트 - 윈도우 설치
echo =====================================================
echo.

REM Python 확인
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python을 찾을 수 없습니다.
    echo     https://www.python.org/downloads/ 에서 Python 3.10+ 설치 후 다시 실행해주세요.
    echo     설치 시 "Add Python to PATH" 체크 필수.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version') do set PYVER=%%v
echo [O] Python !PYVER! 감지

REM ffmpeg 확인
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [!] ffmpeg가 PATH에 없습니다.
    echo     아래 중 하나로 설치하세요:
    echo       - winget install ffmpeg
    echo       - https://ffmpeg.org/download.html
    echo.
    set /p CONT="ffmpeg 없이 설치를 계속할까요? (y/n): "
    if /i not "!CONT!"=="y" exit /b 1
) else (
    echo [O] ffmpeg 감지
)

REM 가상환경 생성
if not exist venv (
    echo.
    echo [.] 가상환경 생성 중...
    python -m venv venv
    if errorlevel 1 (
        echo [X] venv 생성 실패
        pause
        exit /b 1
    )
)
echo [O] 가상환경 준비 완료

REM 의존성 설치
echo.
echo [.] 패키지 설치 중... (몇 분 걸릴 수 있습니다)
call venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
    echo [X] 패키지 설치 실패
    pause
    exit /b 1
)

REM GPU(CUDA) 감지 안내
echo.
nvidia-smi >nul 2>&1
if not errorlevel 1 (
    echo [O] NVIDIA GPU 감지 - CUDA 가속 사용 가능
    echo     처음 STT 실행 시 cuBLAS/cuDNN 라이브러리가 필요할 수 있습니다.
    echo     필요 시 https://developer.nvidia.com 참고.
) else (
    echo [!] NVIDIA GPU 미감지 - CPU 모드로 동작 (STT 느림)
    echo     긴 방송은 모델을 medium으로 낮추는 것을 권장합니다.
)

echo.
echo =====================================================
echo   설치 완료!
echo =====================================================
echo.
echo 다음 단계:
echo   1. 본인 방송 폴더(예: 내방송\) 에 이 키트의 AGENTS.md 복사
echo   2. YYMMDD 폴더 만들고 source.url 작성
echo   3. Claude Code 또는 Codex 데스크톱으로 폴더 열기
echo   4. "260504 방송 처리해줘" 같은 자연어 명령 실행
echo.
echo 자세한 내용은 README.md 참고.
echo.
pause
