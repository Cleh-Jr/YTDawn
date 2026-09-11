@echo off
title YTDawn Launcher
cd /d "%~dp0"
if exist "YTDawn.exe" (
    start "" "YTDawn.exe"
) else (
    start "" pyw main.py
)
