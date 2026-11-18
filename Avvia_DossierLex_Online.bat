@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ==============================================================================
echo   DossierLex - Avvio Stack Docker + Tunnel HTTPS Tailscale Funnel (:10000)
echo   Studio Legale Avv. Aurelio Bentivegna
echo ==============================================================================
echo.

pushd "%~dp0" >nul 2>&1

echo [1/3] Verifica / Avvio container Docker DossierLex...
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3001/' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 (
    echo     Container frontend gia attivo su http://127.0.0.1:3001
) else (
    docker compose up -d
    if errorlevel 1 (
        echo     Provo avvio tramite WSL Ubuntu...
        wsl -e bash -lc "cd /home/giuseppe/PraticaDebitiAI && docker compose up -d"
        if errorlevel 1 (
            echo [ERRORE] Impossibile avviare Docker Compose. Verifica che Docker Desktop sia aperto.
            popd >nul 2>&1
            pause
            exit /b 1
        )
    )
)

echo [2/3] Attesa disponibilita frontend su http://127.0.0.1:3001 ...
set /a TRIES=0
:wait_loop
set /a TRIES+=1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3001/' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto frontend_ready
if %TRIES% GEQ 20 (
    echo [AVVISO] Il frontend su porta 3001 non risponde ancora, provo comunque a configurare Funnel...
    goto start_funnel
)
timeout /t 2 /nobreak >nul
goto wait_loop

:frontend_ready
echo     Frontend pronto su http://127.0.0.1:3001

:start_funnel
echo [3/3] Attivazione Tailscale Funnel HTTPS (porta 10000 -^> http://127.0.0.1:3001)...
set "TS_EXE="
for /f "delims=" %%T in ('where tailscale 2^>nul') do (
    if not defined TS_EXE set "TS_EXE=%%T"
)
if not defined TS_EXE (
    if exist "C:\Program Files\Tailscale\tailscale.exe" set "TS_EXE=C:\Program Files\Tailscale\tailscale.exe"
)
if not defined TS_EXE (
    if exist "C:\Program Files (x86)\Tailscale\tailscale.exe" set "TS_EXE=C:\Program Files (x86)\Tailscale\tailscale.exe"
)

if not defined TS_EXE (
    echo [ERRORE] tailscale.exe non trovato. Installa/avvia Tailscale su Windows.
    popd >nul 2>&1
    pause
    exit /b 1
)

echo     Uso binario: "%TS_EXE%"
"%TS_EXE%" funnel --bg --https=10000 http://127.0.0.1:3001
if errorlevel 1 (
    echo.
    echo [ATTENZIONE] Comando Tailscale Funnel terminato con errore.
    echo Se Tailscale mostra un link "https://login.tailscale.com/..." sopra,
    echo aprilo nel browser per abilitare HTTPS/Funnel sul tuo account Tailscale,
    echo poi riesegui questo script.
)

echo.
echo Stato attuale Funnel:
"%TS_EXE%" funnel status
set "EMBED_READONLY_TOKEN="
set "ADMIN_TOKEN="
if exist ".env.local" (
    for /f "usebackq tokens=1,* delims==" %%A in (".env.local") do (
        if "%%A"=="EMBED_READONLY_TOKEN" set "EMBED_READONLY_TOKEN=%%B"
        if "%%A"=="ADMIN_TOKEN" set "ADMIN_TOKEN=%%B"
    )
)
echo.
echo ==============================================================================
if defined EMBED_READONLY_TOKEN (
    echo   URL HTTPS Iframe CRM:
    echo   https://evo-x2.tail723056.ts.net:10000/embed?token=!EMBED_READONLY_TOKEN!
) else (
    echo   URL HTTPS Iframe CRM: https://evo-x2.tail723056.ts.net:10000/embed
)
echo.
if defined ADMIN_TOKEN (
    echo   URL HTTPS Schermo Intero:
    echo   https://evo-x2.tail723056.ts.net:10000/?access_token=!ADMIN_TOKEN!
) else (
    echo   URL HTTPS Schermo Intero: https://evo-x2.tail723056.ts.net:10000/
)
echo ==============================================================================
popd >nul 2>&1
pause
