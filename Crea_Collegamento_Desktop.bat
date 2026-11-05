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

echo [1/2] Rilevamento cartella Desktop...
set "DESKTOP_DIR="
for /f "tokens=2*" %%A in ('reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders" /v Desktop 2^>nul') do (
    set "RAW_DESKTOP=%%B"
)
if defined RAW_DESKTOP (
    call set "DESKTOP_DIR=%RAW_DESKTOP%"
)
if not defined DESKTOP_DIR (
    if exist "%USERPROFILE%\OneDrive\Desktop" (
        set "DESKTOP_DIR=%USERPROFILE%\OneDrive\Desktop"
    ) else if exist "%USERPROFILE%\Desktop" (
        set "DESKTOP_DIR=%USERPROFILE%\Desktop"
    ) else (
        set "DESKTOP_DIR=%USERPROFILE%\Desktop"
    )
)
if not exist "%DESKTOP_DIR%" mkdir "%DESKTOP_DIR%" 2>nul

echo [2/2] Generazione collegamento con icona e avvio silenzioso...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$targetDir = '%DESKTOP_DIR%'.Trim(); " ^
  "try { " ^
  "  $ws = New-Object -ComObject WScript.Shell; " ^
  "  $shDesktop = $ws.SpecialFolders.Item('Desktop'); " ^
  "  if ($shDesktop -and (Test-Path $shDesktop)) { $targetDir = $shDesktop }; " ^
  "  if (-not (Test-Path $targetDir)) { [System.IO.Directory]::CreateDirectory($targetDir) | Out-Null }; " ^
  "  $lnk = Join-Path $targetDir 'DossierLex.lnk'; " ^
  "  $s = $ws.CreateShortcut($lnk); " ^
  "  $s.TargetPath = 'wscript.exe'; " ^
  "  $s.Arguments = '\"%TARGET_VBS%\"'; " ^
  "  $s.WorkingDirectory = '%SCRIPT_DIR%'; " ^
  "  if (Test-Path '%ICON_FILE%') { $s.IconLocation = '%ICON_FILE%,0' }; " ^
  "  $s.Description = 'DossierLex - Studio Legale Bentivegna'; " ^
  "  $s.Save(); " ^
  "  $altDirs = @((Join-Path $env:USERPROFILE 'Desktop'), (Join-Path $env:USERPROFILE 'OneDrive\Desktop')); " ^
  "  foreach ($ad in $altDirs) { " ^
  "    if ((Test-Path $ad) -and ($ad -ne $targetDir)) { " ^
  "      Copy-Item $lnk (Join-Path $ad 'DossierLex.lnk') -Force -ErrorAction SilentlyContinue; " ^
  "    } " ^
  "  }; " ^
  "  exit 0; " ^
  "} catch { " ^
  "  Write-Host ('Errore: ' + $_.Exception.Message); " ^
  "  exit 1; " ^
  "}"

set "SHORTCUT_CREATED=0"
if exist "%DESKTOP_DIR%\DossierLex.lnk" set "SHORTCUT_CREATED=1"
if exist "%USERPROFILE%\Desktop\DossierLex.lnk" set "SHORTCUT_CREATED=1"
if exist "%USERPROFILE%\OneDrive\Desktop\DossierLex.lnk" set "SHORTCUT_CREATED=1"

if "%SHORTCUT_CREATED%"=="1" (
    echo.
    echo ==============================================================================
    echo   [OK] Collegamento creato con successo sul tuo Desktop:
    echo        "%DESKTOP_DIR%\DossierLex.lnk"
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

