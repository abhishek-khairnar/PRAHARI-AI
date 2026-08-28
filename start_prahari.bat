@echo off
setlocal enabledelayedexpansion

title PRAHARI-AI Multi-Camera Intelligent Surveillance Platform

echo ==============================================================================
echo  PRAHARI-AI — Multi-Camera AI Surveillance Command Center
echo ==============================================================================
echo.

:: Detect Project Root
cd /d "%~dp0"
set "PROJECT_ROOT=%CD%"
echo [*] Project Root: %PROJECT_ROOT%

:: Check Python installation
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not found in PATH! Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: Verify dependencies
echo [*] Checking Python dependencies...
python -c "import fastapi, uvicorn, cv2, torch, ultralytics; print('Dependencies OK')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Missing some required dependencies. Installing requirements.txt...
    pip install -r requirements.txt
)

:: Check CUDA GPU
python -c "import torch; print(f'[*] AI Inference Engine: CUDA GPU Accelerated ({torch.cuda.get_device_name(0)})' if torch.cuda.is_available() else '[!] AI Inference Engine: CPU Fallback')"

:: Check video files
echo [*] Checking multi-camera demo video feeds...
if exist "demo_videos\border_demo.mp4" (
    echo     [+] CAM-01: demo_videos\border_demo.mp4 [FOUND]
) else (
    echo     [!] CAM-01: border_demo.mp4 not found in demo_videos\
)
if exist "demo_videos\night_demo.mp4" (
    echo     [+] CAM-02: demo_videos\night_demo.mp4 [FOUND]
)
if exist "demo_videos\activity-demo.mp4" (
    echo     [+] CAM-03: demo_videos\activity-demo.mp4 [FOUND]
) else if exist "demo_videos\activity_demo.mp4" (
    echo     [+] CAM-03: demo_videos\activity_demo.mp4 [FOUND]
)
if exist "demo_videos\cctv_demo.mp4" (
    echo     [+] CAM-04: demo_videos\cctv_demo.mp4 [FOUND]
)

echo.
echo ==============================================================================
echo  Starting PRAHARI-AI Server on http://localhost:8001
echo ==============================================================================
echo.

:: Start server in background and open browser when ready
start "" cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8001"
python main.py

pause
