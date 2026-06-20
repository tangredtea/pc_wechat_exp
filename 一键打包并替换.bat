@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo   WeChat EXP - 一键打包并替换下载目录 exe
echo ============================================================
echo.

cd /d "%~dp0"
call build.bat
if %errorlevel% neq 0 (
    echo [!] 打包失败
    pause
    exit /b 1
)

set "TARGET=%USERPROFILE%\Downloads\wechat_history_export.exe"
set "BUILT="
for %%F in ("%~dp0dist\wechat_exp_*.exe") do set "BUILT=%%~fF"

if not defined BUILT (
    if exist "%~dp0dist\wechat_exp.exe" set "BUILT=%~dp0dist\wechat_exp.exe"
)

if not defined BUILT (
    echo [!] 未找到 dist\wechat_exp_*.exe
    pause
    exit /b 1
)

echo.
echo [*] 复制到: %TARGET%
copy /Y "%BUILT%" "%TARGET%" >nul
if %errorlevel% neq 0 (
    echo [!] 复制失败，请手动将以下文件复制到下载目录:
    echo     %BUILT%
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   完成!
echo   已替换: %TARGET%
echo   源文件: %BUILT%
echo ============================================================
echo.
pause
