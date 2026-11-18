@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ==============================================================================
echo   DossierLex - Avvio Stack Docker + Tunnel HTTPS Tailscale Funnel (:10000)
echo   Studio Legale Avv. Aurelio Bentivegna
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/3] Avvio container Docker DossierLex...
docker compose up -d
if errorlevel 1 (
    echo [ERRORE] Impossibile avviare Docker Compose. Verifica che Docker Desktop sia aperto.
    pause
    exit /b 1
)

echo [2/3] Attesa disponibilità frontend su http://127.0.0.1:3001 ...
set /a TRIES=0
:wait_loop
set /a TRIES+=1
powershell -NoProfile -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:3001/' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if %errorlevel%==0 goto frontend_ready
if %TRIES% GEQ 20 (
    echo [AVVISO] Il frontend su porta 3001 sta ancora completando l'avvio, proseguo con Funnel...
    goto start_funnel
)
timeout /t 2 /nobreak >nul
goto wait_loop

:frontend_ready
echo     Frontend pronto su http://127.0.0.1:3001

:start_funnel
echo [3/3] Attivazione Tailscale Funnel HTTPS (porta 10000 -> 127.0.0.1:3001)...
where tailscale >nul 2>&1
if errorlevel 1 (
    if exist "C:\Program Files\Tailscale\tailscale.exe" (
        "C:\Program Files\Tailscale\tailscale.exe" funnel --bg --https=10000 3001
    ) else (
        echo [ERRORE] Comando tailscale non trovato nel PATH. Avvia Tailscale su Windows e riprova:
        echo          tailscale funnel --bg --https=10000 3001
        pause
        exit /b 1
    )
) else (
    tailscale funnel --bg --https=10000 3001
)

echo.
echo Verifica stato Funnel:
tailscale funnel status 2>nul
echo.
echo DossierLex online su: https://evo-x2.tail723056.ts.net:10000
echo ==============================================================================
pause
