@echo off
chcp 65001 >nul
setlocal

echo.
echo ============================================================
echo   WeChat EXP - PyInstaller Build Script
echo ============================================================
echo.

pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller not found, installing...
    pip install pyinstaller
)

echo [*] Installing dependencies...
pip install -r requirements.txt

echo.
echo [*] Building...
echo.

pyinstaller --onefile --console --name wechat_exp --add-data "src;src" --hidden-import Crypto.Cipher.AES --hidden-import openpyxl --hidden-import jieba --hidden-import jieba.posseg --collect-all jieba src/main.py

echo.
echo ============================================================
echo   Build complete!
echo   Output: dist\wechat_exp.exe
echo ============================================================
pause
