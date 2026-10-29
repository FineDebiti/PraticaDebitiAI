@echo off
chcp 65001 >nul
echo ==============================================================================
echo   DossierLex - Creazione Collegamento Desktop in "Modalità App"
echo   Studio Legale Avv. Aurelio Bentivegna
echo ==============================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "ICON_FILE=%SCRIPT_DIR%DossierLex.ico"
set "TARGET_VBS=%SCRIPT_DIR%DossierLex_Avvio_Silenzioso.vbs"

echo [1/2] Configurazione percorso collegamento...
set "DESKTOP_DIR=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP_DIR%\DossierLex.lnk"

echo [2/2] Generazione collegamento con icona e avvio silenzioso...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$s = $ws.CreateShortcut('%SHORTCUT%'); " ^
  "$s.TargetPath = 'wscript.exe'; " ^
  "$s.Arguments = '\"%TARGET_VBS%\"'; " ^
  "$s.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "$s.IconLocation = '%ICON_FILE%,0'; " ^
  "$s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
  "$s.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo ==============================================================================
    echo   [OK] Collegamento creato con successo sul tuo Desktop:
    echo        "%SHORTCUT%"
    echo.
    echo   Da adesso puoi avviare DossierLex semplicemente con doppio clic
    echo   sull'icona DossierLex sul tuo Desktop!
    echo   Nessuna finestra nera del terminale si aprirà.
    echo ==============================================================================
) else (
    echo.
    echo [ERRORE] Impossibile creare il collegamento sul Desktop.
)

echo.
pause

