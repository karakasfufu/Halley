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
echo BIST Haber Radari aciliyor... Kapatmak icin bu pencereyi kapatin.
rem Eksik KAP sayfalarini tarayici acik olmasa da tamamlayan bekci (ayni pencerede, pencere kapaninca biter)
start "" /b "%VENV%\Scripts\python" -m bist_haber okuyucu
"%VENV%\Scripts\python" -m streamlit run app.py
