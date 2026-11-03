#!/bin/bash
# ==============================================================================
# DossierLex - Installatore Applicazione per Apple Mac (macOS)
# Studio Legale Avv. Aurelio Bentivegna
# ==============================================================================

# Risolvi la cartella dello script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_DIR="$HOME/Desktop"
APP_PATH="$DESKTOP_DIR/DossierLex.app"

echo "=============================================================================="
echo "  DossierLex - Creazione Applicazione per Mac"
echo "  Studio Legale Avv. Aurelio Bentivegna"
echo "=============================================================================="
echo ""
echo "Configurazione dell'applicazione sul Desktop del tuo Mac in corso..."

# 1. Rimuovi eventuale versione precedente
rm -rf "$APP_PATH"

# 2. Crea la struttura del bundle nativo .app per macOS
mkdir -p "$APP_PATH/Contents/MacOS"
mkdir -p "$APP_PATH/Contents/Resources"

# 3. Crea Info.plist
cat << 'EOF' > "$APP_PATH/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>dossierlex_launcher</string>
    <key>CFBundleIconFile</key>
    <string>app.icns</string>
    <key>CFBundleIdentifier</key>
    <string>it.studiobentivegna.dossierlex</string>
    <key>CFBundleName</key>
    <string>DossierLex</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF

# 4. Crea lo script di avvio intelligente (Auto-Switch Ufficio / Remoto)
cat << 'EOF' > "$APP_PATH/Contents/MacOS/dossierlex_launcher"
#!/bin/bash
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
EOF

chmod +x "$APP_PATH/Contents/MacOS/dossierlex_launcher"

# 5. Copia l'icona ufficiale se presente
if [ -f "$SCRIPT_DIR/DossierLex.icns" ]; then
    cp "$SCRIPT_DIR/DossierLex.icns" "$APP_PATH/Contents/Resources/app.icns"
fi

# 6. Aggiorna la cache delle icone di macOS per il file .app
touch "$APP_PATH"

echo ""
echo "=============================================================================="
echo "  [OK] Applicazione 'DossierLex.app' creata con successo sul tuo Desktop!"
echo ""
echo "  Come funziona:"
echo "  • In Studio: rileva in automatico la rete Wi-Fi dell'ufficio e si apre subito."
echo "  • Da Casa / Remoto: rileva in automatico Tailscale e si apre subito."
echo "  • Non devi digitare nessun indirizzo IP: basta cliccare sull'icona!"
echo "=============================================================================="
echo ""
read -r -p "Premi INVIO per chiudere questa finestra..."
