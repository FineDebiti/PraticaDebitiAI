#!/bin/bash
cd "$(dirname "$0")"

echo "============================================================"
echo "  PRATICA DEBITI AI - Avvio applicazione (locale, offline)"
echo "============================================================"
echo ""

# --- 1) Verifica che Docker sia installato e in esecuzione ---
if ! docker version >/dev/null 2>&1; then
  echo "[ERRORE] Docker non risulta in esecuzione."
  echo "Apri \"Docker Desktop\", aspetta che sia avviato, poi rilancia questo file."
  echo ""
  read -r -p "Premi INVIO per chiudere..."
  exit 1
fi

echo "[1/3] Costruzione e avvio dei servizi (la PRIMA volta puo' richiedere"
echo "      diversi minuti: scarica e compila tutto. Le volte dopo e' veloce)..."
echo ""
if ! docker compose -f docker-compose.local.yml up -d --build; then
  echo ""
  echo "[ERRORE] Avvio non riuscito. Controlla i messaggi qui sopra."
  read -r -p "Premi INVIO per chiudere..."
  exit 1
fi

echo ""
echo "[2/3] Attendo che l'applicazione sia pronta..."
tries=0
until curl -s -o /dev/null http://localhost:8000/api/health; do
  tries=$((tries + 1))
  if [ "$tries" -ge 60 ]; then
    echo "[AVVISO] L'app ci mette piu' del previsto. Provo comunque ad aprirla."
    break
  fi
  sleep 2
done
if [ "$tries" -lt 60 ]; then
  echo "      Pronta."
  if [ -f "backup.sql" ]; then
    echo "      Caricamento dati di prova (Traietti Alessandro e Planeta S.r.l.)..."
    docker compose -f docker-compose.local.yml exec -T db psql -U pratica pratica_debiti < backup.sql >/dev/null 2>&1 || true
  fi
fi

echo ""
echo "[3/3] Apro l'applicazione nel browser..."
open http://localhost:3000

echo ""
echo "============================================================"
echo "  App avviata.  Indirizzo: http://localhost:3000"
echo "  Per spegnerla:  doppio clic su \"ferma.command\""
echo "============================================================"
echo ""
read -r -p "Premi INVIO per chiudere questa finestra..."
