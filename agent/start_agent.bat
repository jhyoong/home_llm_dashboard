@echo off
REM Home LLM Dashboard - Agent Startup Script for Windows
REM This script sets up and runs the monitoring agent

setlocal enabledelayedexpansion

cd /d "%~dp0"

echo.
echo ========================================
echo   Home LLM Dashboard - Agent Startup
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is required but not installed.
    echo.
    echo Installation instructions:
    echo   1. Download Python from https://python.org
    echo   2. Make sure to check "Add Python to PATH" during installation
    echo   3. Restart this script
    echo.
    pause
    exit /b 1
)

REM Get Python version
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [INFO] Python found: %PYTHON_VERSION%

REM Check if pip is available
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is required but not installed.
    echo Please reinstall Python with pip included.
    pause
    exit /b 1
)

REM Parse command line arguments
set "INSTALL_ONLY="
set "TEST_ONLY="
set "NO_DEPS="
set "SHOW_HELP="

:parse_args
if "%~1"=="" goto :done_parsing
if "%~1"=="--install-only" set "INSTALL_ONLY=1"
if "%~1"=="--test-only" set "TEST_ONLY=1" 
if "%~1"=="--no-deps" set "NO_DEPS=1"
if "%~1"=="--help" set "SHOW_HELP=1"
if "%~1"=="-h" set "SHOW_HELP=1"
shift
goto :parse_args
:done_parsing

if defined SHOW_HELP (
    echo Usage: %~nx0 [OPTIONS]
    echo.
    echo Options:
    echo   --install-only    Only install dependencies and setup config
    echo   --test-only       Only test connection to dashboard
    echo   --no-deps         Skip dependency installation
    echo   --help, -h        Show this help message
    echo.
    echo Default: Install dependencies, setup config, test connection, and run agent
    echo.
    pause
    exit /b 0
)

REM Install dependencies function
:install_dependencies
if defined NO_DEPS goto :setup_config

echo [INFO] Installing/updating dependencies...

if exist "requirements.txt" (
    pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
    echo [INFO] Dependencies installed successfully
) else (
    echo [WARN] requirements.txt not found, installing basic dependencies...
    pip install psutil requests
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install basic dependencies
        pause
        exit /b 1
    )
    
    REM Check for NVIDIA GPU
    nvidia-smi >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] NVIDIA GPU detected, installing GPU monitoring support...
        pip install pynvml
        if !errorlevel! neq 0 (
            echo [WARN] Failed to install pynvml, GPU monitoring may not work
        )
    )
)

if defined INSTALL_ONLY goto :end_script

REM Setup configuration function
:setup_config
if not exist "agent_config.ini" (
    if exist "agent_config.ini.example" (
        echo [INFO] Creating agent_config.ini from example...
        copy "agent_config.ini.example" "agent_config.ini" >nul
    ) else (
        echo [INFO] Creating default configuration...
        python agent.py --create-config
        if !errorlevel! neq 0 (
            echo [ERROR] Failed to create configuration
            pause
            exit /b 1
        )
    )
    
    echo.
    echo [WARN] Please edit agent_config.ini with your dashboard server settings:
    echo [WARN]   server_ip = YOUR_DASHBOARD_SERVER_IP
    echo [WARN]   server_port = 3030
    echo [WARN]   time_period = 5
    echo.
    echo Opening notepad to edit the configuration file...
    notepad "agent_config.ini"
    echo.
    pause
) else (
    echo [INFO] Configuration file found: agent_config.ini
)

if defined TEST_ONLY goto :test_connection
if defined INSTALL_ONLY goto :end_script

REM Test connection function  
:test_connection
echo [INFO] Testing connection to dashboard server...
python agent.py --test-connection
if %errorlevel% equ 0 (
    echo [INFO] Connection test successful!
    if defined TEST_ONLY goto :end_script
) else (
    echo [ERROR] Connection test failed!
    echo.
    echo [WARN] Please check:
    echo [WARN]   1. Dashboard server is running
    echo [WARN]   2. server_ip in agent_config.ini is correct  
    echo [WARN]   3. Network connectivity between machines
    echo [WARN]   4. Firewall settings allow port 3030
    echo.
    if defined TEST_ONLY goto :end_script
    echo [ERROR] Cannot start agent due to connection issues
    echo [INFO] Run '%~nx0 --test-only' after fixing the connection issues
    pause
    exit /b 1
)

REM Run agent function
:run_agent
echo.
echo [INFO] Starting monitoring agent...
echo [INFO] Press Ctrl+C to stop the agent
echo.

python agent.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Agent stopped with error code %errorlevel%
    pause
)

:end_script
echo.
echo Agent script completed.
if not defined TEST_ONLY if not defined INSTALL_ONLY pause
exit /b 0