@echo off
chcp 65001 >nul
echo Arresto dei servizi DossierLex in corso...
cd /d "%~dp0"
docker compose -f docker-compose.local.yml down
echo.
echo [OK] DossierLex arrestato.
pause

