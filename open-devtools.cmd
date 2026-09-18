@echo off
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\WeChatDevTools\cli.bat" (
 call "%LOCALAPPDATA%\Programs\WeChatDevTools\cli.bat" open --project "%~dp0miniprogram"
) else (
 echo Open WeChat Developer Tools and import:
 echo %~dp0miniprogram
 pause
)
