@echo off
echo ===================================================
echo   Edge TTS Wizard - PyInstaller Build Script
echo ===================================================
echo.

REM 1. Check and download FFmpeg if necessary
echo [*] Checking for FFmpeg...
if not exist "ffmpeg.exe" (
    echo [!] ffmpeg.exe not found!
    echo [*] Downloading FFmpeg from BtbN GitHub release, this may take a minute...
    curl -L -o ffmpeg.zip "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    echo [*] Extracting FFmpeg...
    tar -xf ffmpeg.zip
    
    echo [*] Copying executables...
    copy /y "ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" . >nul
    copy /y "ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" . >nul
    
    echo [*] Cleaning up downloaded files...
    rmdir /s /q "ffmpeg-master-latest-win64-gpl"
    del /q "ffmpeg.zip"
    echo [*] FFmpeg setup complete!
) else (
    echo [*] FFmpeg found!
)
echo.

REM 2. Get customtkinter installation path dynamically
echo [*] Finding customtkinter installation path...
FOR /F "tokens=*" %%i IN ('python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"') DO SET CTK_PATH=%%i

if "%CTK_PATH%"=="" (
    echo [ERROR] customtkinter path not found. Please ensure it is installed.
    echo Please run: pip install customtkinter
    pause
    exit /b 1
)
echo [*] Found path: %CTK_PATH%
echo.

REM 3. Run PyInstaller
echo [*] Running PyInstaller...
REM Use --collect-all for customtkinter and other hidden dependencies
REM Pack everything into a SINGLE executable (--onefile) and embed ffmpeg tools
pyinstaller --noconfirm --onefile --windowed --name "Edge_TTS_Wizard" --add-data "%CTK_PATH%";customtkinter/ --add-data "ffmpeg.exe;." --add-data "ffprobe.exe;." --collect-all edge_tts --collect-all sounddevice --collect-all pydub main.py

REM 4. Post-build instructions
echo.
echo ===================================================
echo [*] Build Complete!
echo.
echo You can now share "dist\Edge_TTS_Wizard.exe" with anyone!
echo ffmpeg and dependencies are completely embedded inside the file.
echo ===================================================
echo.

pause
