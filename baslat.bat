@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "VENV=%USERPROFILE%\.venvs\bist-haber"
if not exist "%VENV%\Scripts\python.exe" (
    echo Ilk kurulum yapiliyor, birkac dakika surebilir...
    python -m venv "%VENV%" || (echo Python bulunamadi. python.org'dan Python 3.9+ kurun. & pause & exit /b 1)
    "%VENV%\Scripts\python" -m pip install --upgrade pip
    "%VENV%\Scripts\pip" install -r requirements.txt || (echo Kurulum basarisiz. & pause & exit /b 1)
)
rem 2026-11-09: Halley zaten aciksa ikinci kopya baslatma ("Port 8501 is already in use" yerine acik paneli goster)
powershell -NoProfile -Command "try { if ((Invoke-WebRequest -UseBasicParsing http://localhost:8501/_stcore/health -TimeoutSec 3).Content -eq 'ok') { exit 0 } } catch {}; exit 1"
if %errorlevel%==0 (
    echo Halley zaten acik; panel tarayicida aciliyor.
    start "" http://localhost:8501
    timeout /t 3 >nul
    exit /b 0
)
echo BIST Haber Radari aciliyor... Kapatmak icin bu pencereyi kapatin.
rem Eksik KAP sayfalarini tarayici acik olmasa da tamamlayan bekci (ayni pencerede, pencere kapaninca biter)
start "" /b "%VENV%\Scripts\python" -m bist_haber okuyucu
"%VENV%\Scripts\python" -m streamlit run app.py
