@echo off
chcp 65001 >nul
echo ==============================================================================
echo   DossierLex - Configurazione Postazione Colleghi
echo   Studio Legale Avv. Aurelio Bentivegna
echo ==============================================================================
echo.
echo Questa procedura crea il collegamento sul Desktop di questo computer per accedere
echo a DossierLex in esecuzione sul Server principale dello studio.
echo Non e' necessario installare Docker, Python o altri componenti pesanti.
echo.
echo ------------------------------------------------------------------------------
echo   INDIRIZZO IP DEL SERVER DI STUDIO:
echo   - In Studio (Wi-Fi o Cavo LAN):   192.168.1.31   [PREDEFINITO]
echo   - Da Casa / Remoto (Tailscale):   100.80.46.116
echo ------------------------------------------------------------------------------
echo.
set "SERVER_IP=192.168.1.31"
set /p "USER_INPUT=Inserisci l'IP del Server [Premi INVIO per usare 192.168.1.31]: "
if not "%USER_INPUT%"=="" set "SERVER_IP=%USER_INPUT%"

:: Pulizia da eventuali prefissi, suffissi o spazi digitati per errore
set "SERVER_IP=%SERVER_IP:http://=%"
set "SERVER_IP=%SERVER_IP:https://=%"
set "SERVER_IP=%SERVER_IP::3001=%"
set "SERVER_IP=%SERVER_IP:/=%"
set "SERVER_IP=%SERVER_IP: =%"

:: Salva l'icona in una cartella permanente del collega
set "APP_DIR=%LOCALAPPDATA%\DossierLex"
if not exist "%APP_DIR%" mkdir "%APP_DIR%"

if exist "%~dp0DossierLex.ico" (
    copy /y "%~dp0DossierLex.ico" "%APP_DIR%\DossierLex.ico" >nul 2>&1
)
set "PERM_ICON=%APP_DIR%\DossierLex.ico"

:: Rilevamento browser: cerca prima Google Chrome, poi Edge
set "BROWSER_EXE="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if "%BROWSER_EXE%"=="" if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if "%BROWSER_EXE%"=="" if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if "%BROWSER_EXE%"=="" if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "BROWSER_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if "%BROWSER_EXE%"=="" if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "BROWSER_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set "DESKTOP_DIR=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP_DIR%\DossierLex.lnk"
set "TARGET_URL=http://%SERVER_IP%:3001"

echo Generazione del collegamento Desktop...

if not "%BROWSER_EXE%"=="" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws = New-Object -ComObject WScript.Shell; " ^
      "$s = $ws.CreateShortcut('%SHORTCUT%'); " ^
      "$s.TargetPath = '%BROWSER_EXE%'; " ^
      "$s.Arguments = '%TARGET_URL%'; " ^
      "$s.WorkingDirectory = '%USERPROFILE%'; " ^
      "if (Test-Path '%PERM_ICON%') { $s.IconLocation = '%PERM_ICON%,0' }; " ^
      "$s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
      "$s.Save()"
) else (
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ws = New-Object -ComObject WScript.Shell; " ^
      "$s = $ws.CreateShortcut('%SHORTCUT%'); " ^
      "$s.TargetPath = '%TARGET_URL%'; " ^
      "if (Test-Path '%PERM_ICON%') { $s.IconLocation = '%PERM_ICON%,0' }; " ^
      "$s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
      "$s.Save()"
)

echo.
echo ==============================================================================
echo   [OK] Collegamento DossierLex creato con successo sul tuo Desktop!
echo        Indirizzo del server: %TARGET_URL%
echo.
echo   Puoi fare doppio clic sull'icona DossierLex per iniziare a lavorare.
echo ==============================================================================
echo.
pause
