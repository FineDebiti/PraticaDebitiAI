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

:: Rilevamento cartella Desktop (supporto OneDrive, cartelle reindirizzate e Windows in italiano)
set "DESKTOP_DIR="

:: 1. Interroga il registro per trovare la cartella Desktop effettiva dell'utente
for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do (
    set "RAW_DESKTOP=%%B"
)
if defined RAW_DESKTOP (
    call set "DESKTOP_DIR=%RAW_DESKTOP%"
)

:: 2. Se non presente nel registro o non valida, verifica percorsi comuni (OneDrive / standard)
if not defined DESKTOP_DIR (
    if exist "%USERPROFILE%\OneDrive\Desktop" (
        set "DESKTOP_DIR=%USERPROFILE%\OneDrive\Desktop"
    ) else if exist "%USERPROFILE%\OneDrive\Scrivania" (
        set "DESKTOP_DIR=%USERPROFILE%\OneDrive\Scrivania"
    ) else if exist "%USERPROFILE%\Desktop" (
        set "DESKTOP_DIR=%USERPROFILE%\Desktop"
    ) else if exist "%USERPROFILE%\Scrivania" (
        set "DESKTOP_DIR=%USERPROFILE%\Scrivania"
    ) else (
        set "DESKTOP_DIR=%USERPROFILE%\Desktop"
    )
)

:: Assicura che la directory Desktop esista fisicamente
if not exist "%DESKTOP_DIR%" mkdir "%DESKTOP_DIR%" 2>nul

set "TARGET_URL=http://%SERVER_IP%:3001"

echo Generazione del collegamento Desktop in corso...

:: Esecuzione PowerShell con rilevamento dinamico della shell e gestione sicura delle cartelle
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$targetDir = '%DESKTOP_DIR%'.Trim(); " ^
  "try { " ^
  "  $ws = New-Object -ComObject WScript.Shell; " ^
  "  $shDesktop = $ws.SpecialFolders.Item('Desktop'); " ^
  "  if ($shDesktop -and (Test-Path $shDesktop)) { $targetDir = $shDesktop }; " ^
  "  if (-not (Test-Path $targetDir)) { [System.IO.Directory]::CreateDirectory($targetDir) | Out-Null }; " ^
  "  $lnk = Join-Path $targetDir 'DossierLex.lnk'; " ^
  "  $s = $ws.CreateShortcut($lnk); " ^
  "  $browser = '%BROWSER_EXE%'; " ^
  "  $url = '%TARGET_URL%'; " ^
  "  $icon = '%PERM_ICON%'; " ^
  "  if ($browser -and (Test-Path $browser)) { " ^
  "    $s.TargetPath = $browser; " ^
  "    $s.Arguments = $url; " ^
  "    $s.WorkingDirectory = $env:USERPROFILE; " ^
  "  } else { " ^
  "    $s.TargetPath = $url; " ^
  "  }; " ^
  "  if ($icon -and (Test-Path $icon)) { $s.IconLocation = ($icon + ',0') }; " ^
  "  $s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
  "  $s.Save(); " ^
  "  $altDirs = @((Join-Path $env:USERPROFILE 'Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Scrivania')); " ^
  "  foreach ($ad in $altDirs) { " ^
  "    if ((Test-Path $ad) -and ($ad -ne $targetDir)) { " ^
  "      Copy-Item $lnk (Join-Path $ad 'DossierLex.lnk') -Force -ErrorAction SilentlyContinue; " ^
  "    } " ^
  "  }; " ^
  "  exit 0; " ^
  "} catch { " ^
  "  Write-Host ('Errore PowerShell: ' + $_.Exception.Message); " ^
  "  exit 1; " ^
  "}"

:: Verifica esito e creazione fallback .url in caso di necessita'
set "SHORTCUT_CREATED=0"
if exist "%DESKTOP_DIR%\DossierLex.lnk" set "SHORTCUT_CREATED=1"
if exist "%USERPROFILE%\Desktop\DossierLex.lnk" set "SHORTCUT_CREATED=1"
if exist "%USERPROFILE%\OneDrive\Desktop\DossierLex.lnk" set "SHORTCUT_CREATED=1"
if exist "%USERPROFILE%\OneDrive\Scrivania\DossierLex.lnk" set "SHORTCUT_CREATED=1"

if "%SHORTCUT_CREATED%"=="0" (
    echo [AVVISO] Creazione file .lnk non riuscita, creo collegamento Web diretto (.url)...
    (
      echo [InternetShortcut]
      echo URL=%TARGET_URL%
      echo IconFile=%PERM_ICON%
      echo IconIndex=0
    ) > "%DESKTOP_DIR%\DossierLex.url"

    if exist "%USERPROFILE%\OneDrive\Desktop" (
        copy /y "%DESKTOP_DIR%\DossierLex.url" "%USERPROFILE%\OneDrive\Desktop\DossierLex.url" >nul 2>&1
    )
    if exist "%USERPROFILE%\Desktop" (
        copy /y "%DESKTOP_DIR%\DossierLex.url" "%USERPROFILE%\Desktop\DossierLex.url" >nul 2>&1
    )
    if exist "%DESKTOP_DIR%\DossierLex.url" set "SHORTCUT_CREATED=1"
)

echo.
if "%SHORTCUT_CREATED%"=="1" (
    echo ==============================================================================
    echo   [OK] Collegamento DossierLex creato con successo sul tuo Desktop!
    echo        Posizione rilevata: %DESKTOP_DIR%
    echo        Indirizzo del server: %TARGET_URL%
    echo.
    echo   Puoi fare doppio clic sull'icona DossierLex per iniziare a lavorare.
    echo ==============================================================================
) else (
    echo ==============================================================================
    echo   [ATTENZIONE] Non e' stato possibile creare l'icona sul Desktop.
    echo   Puoi comunque accedere direttamente aprendo Chrome o Edge e digitando:
    echo        %TARGET_URL%
    echo ==============================================================================
)
echo.
pause
