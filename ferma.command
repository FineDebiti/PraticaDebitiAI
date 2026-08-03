#!/bin/bash
cd "$(dirname "$0")"

echo "============================================================"
echo "  PRATICA DEBITI AI - Spegnimento"
echo "============================================================"
echo ""
echo "I dati (pratiche, documenti) restano salvati sul computer."
echo ""

docker compose -f docker-compose.local.yml down

echo ""
echo "App spenta. Per riavviarla: doppio clic su \"avvia.command\"."
echo ""
read -r -p "Premi INVIO per chiudere questa finestra..."
