#!/bin/bash
# ==============================================================================
# DossierLex - Avvio Diretto per Apple Mac (macOS)
# Studio Legale Avv. Aurelio Bentivegna
# ==============================================================================

OFFICE_URL="http://192.168.1.31:3001"
REMOTE_URL="http://100.80.46.116:3001"

# 1. Verifica se sei connesso al Wi-Fi dell'Ufficio
if curl -s -m 1.5 "$OFFICE_URL" >/dev/null 2>&1; then
    open "$OFFICE_URL"
    exit 0
fi

# 2. Se non sei in ufficio, verifica la connessione da Remoto tramite Tailscale
if curl -s -m 2.0 "$REMOTE_URL" >/dev/null 2>&1; then
    open "$REMOTE_URL"
    exit 0
fi

# 3. Se entrambi falliscono, mostra un avviso dettagliato all'utente
osascript -e 'display alert "DossierLex non raggiungibile" message "Non è stato possibile collegarsi al Server di DossierLex.\n\n• In Ufficio: assicurati di essere connesso al Wi-Fi dello studio e che il PC Server sia acceso.\n• Da Remoto / Casa: assicurati che l'\''applicazione Tailscale sia attiva e connessa sul tuo Mac."'
exit 1
