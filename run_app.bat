@echo off
REM Quick launcher for Job Tracker from Command Prompt / double-click

cd /d "%~dp0"

REM Use PowerShell to run the main launcher script
powershell -ExecutionPolicy Bypass -File ".\run_app.ps1"

