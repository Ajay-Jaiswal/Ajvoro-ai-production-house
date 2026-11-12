@echo off
setlocal EnableExtensions

REM AI Influencer Studio - Windows launcher
REM Recommended: Python 3.11 (64-bit)

cd /d "%~dp0"
title AI Influencer Studio

 echo.
echo ================================================
echo          AI INFLUENCER STUDIO
echo ================================================
echo.

REM Ensure the main Streamlit entry point exists.
if not exist "app.py" (
    echo [ERROR] app.py was not found in:
    echo         %CD%
    echo Place start.bat beside app.py and try again.
    goto :error
)

set "VENV_PYTHON=%CD%\venv\Scripts\python.exe"

REM Create the virtual environment if it does not exist.
if not exist "%VENV_PYTHON%" (
    echo [INFO] Creating Python 3.11 virtual environment...
    py -3.11 --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python 3.11 was not found.
        echo Install 64-bit Python 3.11 and enable the Python Launcher.
        echo Download: https://www.python.org/downloads/
        goto :error
    )

    py -3.11 -m venv "%CD%\venv"
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :error
    )
)

REM Confirm that the existing environment uses Python 3.11.
for /f "tokens=2" %%V in ('"%VENV_PYTHON%" --version 2^>^&1') do set "PYTHON_VERSION=%%V"
if not "%PYTHON_VERSION:~0,4%"=="3.11" (
    echo [ERROR] The project's venv uses Python %PYTHON_VERSION%.
    echo This project is configured for Python 3.11.
    echo Rename or remove the venv folder, then run start.bat again.
    goto :error
)

echo [INFO] Using Python %PYTHON_VERSION%.

REM Install requirements only if one or more core imports are missing.
"%VENV_PYTHON%" -c "import importlib.util,sys; names=['streamlit','numpy','PIL','cv2','imageio','imageio_ffmpeg','psutil','pyttsx3','soundfile']; missing=[n for n in names if importlib.util.find_spec(n) is None]; print('Missing packages: '+', '.join(missing) if missing else 'Core packages are ready'); sys.exit(1 if missing else 0)"
if errorlevel 1 (
    if not exist "requirements.txt" (
        echo [ERROR] requirements.txt was not found.
        goto :error
    )
    echo [INFO] Installing project dependencies. This may take a few minutes...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 (
        echo [ERROR] Could not upgrade pip.
        goto :error
    )
    "%VENV_PYTHON%" -m pip install -r "requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Dependency installation failed. Check your internet connection and Python version.
        goto :error
    )
)

echo.
echo [INFO] Starting Streamlit...
echo [INFO] The browser should open automatically.
echo [INFO] Press Ctrl+C in this window to stop the application.
echo.
"%VENV_PYTHON%" -m streamlit run "app.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Streamlit stopped with an error.
    goto :error
)

goto :end

:error
echo.
echo Startup could not continue. Review the message above.
pause

:end
endlocal
