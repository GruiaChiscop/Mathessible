@echo off
rem Prepares a checkout on Windows: runs bootstrap.ps1 beside it (see there).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0bootstrap.ps1" %*
exit /b %ERRORLEVEL%
