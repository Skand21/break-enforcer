@echo off
echo === Break Enforcer Build ===
echo.

echo Installing dependencies...
pip install -r requirements.txt
echo.

echo Building executable...
pyinstaller --noconfirm --windowed --name BreakEnforcer main.py
echo.

if exist "dist\BreakEnforcer\BreakEnforcer.exe" (
    echo Build successful!
    echo Output: dist\BreakEnforcer\BreakEnforcer.exe
    echo.
    echo You can copy the entire dist\BreakEnforcer folder to any PC.
) else (
    echo Build failed. Check errors above.
)

pause
