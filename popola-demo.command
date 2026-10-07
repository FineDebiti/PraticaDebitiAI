#!/bin/bash
cd "$(dirname "$0")"

echo "============================================================"
echo "  Carico una pratica DIMOSTRATIVA (dati fittizi: DEMO-0001)"
echo "============================================================"
echo ""
echo "(L'app deve essere gia' avviata con \"avvia.command\")"
echo ""

if ! docker compose -f docker-compose.local.yml exec backend python seed_demo.py; then
  echo ""
  echo "[ERRORE] Non sono riuscito a caricare la demo."
  echo "Assicurati che l'app sia avviata, poi riprova."
  read -r -p "Premi INVIO per chiudere..."
  exit 1
fi

echo ""
echo "Fatto. Apri http://localhost:3000 e cerca la pratica DEMO-0001."
echo ""
read -r -p "Premi INVIO per chiudere questa finestra..."
