@echo off
chcp 65001 >nul
echo ==============================================================================
echo   DossierLex - Creazione Collegamento per Postazioni Colleghi (Rete Studio)
echo   Studio Legale Avv. Aurelio Bentivegna
echo ==============================================================================
echo.
echo Questa procedura crea il collegamento sul Desktop di questo computer per accedere
echo a DossierLex in esecuzione sul Server principale dello studio.
echo.

set /p SERVER_IP="Inserisci l'indirizzo IP del PC Server (es. 192.168.1.150): "

if "%SERVER_IP%"=="" (
    echo [ERRORE] Indirizzo IP non inserito. Operazione annullata.
    pause
    exit /b 1
)

set "EDGE_EXE="
if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if "%EDGE_EXE%"=="" if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set "DESKTOP_DIR=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP_DIR%\DossierLex.lnk"
set "TARGET_URL=http://%SERVER_IP%:3001"
set "ICON_FILE=%~dp0DossierLex.ico"

echo Generazione collegamento Desktop in Modalità App...

if not "%EDGE_EXE%"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws = New-Object -ComObject WScript.Shell; " ^
      "$s = $ws.CreateShortcut('%SHORTCUT%'); " ^
      "$s.TargetPath = '%EDGE_EXE%'; " ^
      "$s.Arguments = '--app=%TARGET_URL%'; " ^
      "$s.WorkingDirectory = '%USERPROFILE%'; " ^
      "if (Test-Path '%ICON_FILE%') { $s.IconLocation = '%ICON_FILE%,0' }; " ^
      "$s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
      "$s.Save()"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws = New-Object -ComObject WScript.Shell; " ^
      "$s = $ws.CreateShortcut('%SHORTCUT%'); " ^
      "$s.TargetPath = '%TARGET_URL%'; " ^
      "$s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
      "$s.Save()"
)

echo.
echo ==============================================================================
echo   [OK] Collegamento DossierLex creato sul Desktop del collega!
echo        Indirizzo server: %TARGET_URL%
echo ==============================================================================
echo.
pause

