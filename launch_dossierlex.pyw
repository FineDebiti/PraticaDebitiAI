"""
DossierLex - Desktop Launcher Professionale Multi-Browser
Studio Legale Avv. Aurelio Bentivegna

Funzioni:
1. Se DossierLex e' gia' online (porta 3001), apre istantaneamente il browser.
2. Se Docker o il sistema sono spenti, mostra una splash window elegante
   (colori ufficiali verde bosco #3F4A3C e oro #C8A55A dello studio) con stato in tempo reale.
3. Avvia automaticamente Docker Desktop su Windows se e' chiuso.
4. Avvia i container Docker (PostgreSQL, Redis, Backend, Celery, Frontend) in WSL in modalita' invisibile.
5. Rileva tutti i browser installati (Chrome, Brave, Edge, Opera, Firefox) e apre in modalita' App dedicata.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

# Percorsi e Porte
FRONTEND_PORT = 3001
BACKEND_PORT = 8000
APP_URL = f"http://localhost:{FRONTEND_PORT}"
HEALTH_URL = f"http://localhost:{BACKEND_PORT}/api/health"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

SCRIPT_DIR = Path(__file__).resolve().parent
LOG_FILE = SCRIPT_DIR / "launcher.log"


def log(msg: str):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass


def is_backend_ready(timeout: float = 1.0) -> bool:
    """Verifica se il Backend FastAPI (:8000/api/health) e' operativo e risponde 200."""
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def is_frontend_ready(timeout: float = 1.0) -> bool:
    """Verifica se il frontend Next.js su :3001 risponde."""
    try:
        req = urllib.request.Request(APP_URL, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def is_app_ready(timeout: float = 1.0) -> bool:
    """Verifica che sia il Backend (:8000) che il Frontend (:3001) siano entrambi pronti al 100%."""
    return is_backend_ready(timeout) and is_frontend_ready(timeout)


def is_docker_running() -> bool:
    """Verifica se il demone Docker risponde su Windows o tramite WSL."""
    # 1. Verifica tramite socket Windows Docker Desktop
    try:
        with socket.create_connection(("127.0.0.1", 2375), timeout=0.5):
            return True
    except OSError:
        pass

    # 2. Verifica comando docker info in Windows
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=2.5,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 3. Verifica comando docker info in WSL
    try:
        res = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "-u", "giuseppe", "--", "docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
            timeout=2.5,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    return False


def start_docker_desktop():
    """Avvia Docker Desktop su Windows se e' chiuso."""
    local_app = os.environ.get("LocalAppData", "")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")

    candidates = [
        os.path.join(local_app, r"Programs\DockerDesktop\Docker Desktop.exe"),
        os.path.join(prog_files, r"Docker\Docker\Docker Desktop.exe"),
    ]

    for exe in candidates:
        if exe and os.path.isfile(exe):
            log(f"Avvio Docker Desktop da: {exe}")
            try:
                subprocess.Popen(
                    [exe],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                return True
            except Exception as e:
                log(f"Errore avvio Docker Desktop: {e}")
    return False


def start_dossierlex_containers():
    """Avvia i container Docker di DossierLex in background tramite WSL."""
    log("Invio comando avvio container Docker Compose...")
    cmd = [
        "wsl.exe",
        "-d",
        "Ubuntu",
        "-u",
        "giuseppe",
        "--",
        "bash",
        "-lc",
        "cd /home/giuseppe/PraticaDebitiAI && docker compose -f docker-compose.local.yml up -d",
    ]
    try:
        subprocess.Popen(
            cmd,
            creationflags=CREATE_NO_WINDOW,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        log(f"Errore esecuzione docker compose in WSL: {e}")
        return False


def get_installed_browsers():
    """Rileva i browser installati nel sistema in ordine di preferenza."""
    local_app = os.environ.get("LocalAppData", "")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    catalog = [
        # Google Chrome
        ("chrome", os.path.join(prog_files, r"Google\Chrome\Application\chrome.exe")),
        ("chrome", os.path.join(prog_files_x86, r"Google\Chrome\Application\chrome.exe")),
        ("chrome", os.path.join(local_app, r"Google\Chrome\Application\chrome.exe")),
        # Brave Browser
        ("brave", os.path.join(prog_files, r"BraveSoftware\Brave-Browser\Application\brave.exe")),
        ("brave", os.path.join(prog_files_x86, r"BraveSoftware\Brave-Browser\Application\brave.exe")),
        ("brave", os.path.join(local_app, r"BraveSoftware\Brave-Browser\Application\brave.exe")),
        # Microsoft Edge
        ("edge", os.path.join(prog_files_x86, r"Microsoft\Edge\Application\msedge.exe")),
        ("edge", os.path.join(prog_files, r"Microsoft\Edge\Application\msedge.exe")),
        # Opera / Opera GX
        ("opera", os.path.join(local_app, r"Programs\Opera\launcher.exe")),
        ("opera", os.path.join(local_app, r"Programs\Opera GX\launcher.exe")),
        ("opera", os.path.join(prog_files, r"Opera\launcher.exe")),
        # Firefox
        ("firefox", os.path.join(prog_files, r"Mozilla Firefox\firefox.exe")),
        ("firefox", os.path.join(prog_files_x86, r"Mozilla Firefox\firefox.exe")),
    ]

    installed = []
    for b_type, path in catalog:
        if path and os.path.isfile(path):
            if not any(p == path for _, p in installed):
                installed.append((b_type, path))
    return installed


def open_browser_tab(url: str):
    """Apre DossierLex come nuova scheda in Google Chrome (o nel browser preferito) accanto alle altre schede aperte."""
    log(f"Apertura scheda browser per URL: {url}")
    browsers = get_installed_browsers()

    # 1. Cerca prima Google Chrome per aprirlo come scheda accanto alle altre tue applicazioni
    for b_type, exe in browsers:
        if b_type == "chrome":
            try:
                subprocess.Popen(
                    [exe, url],
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                )
                log(f"Aperta nuova scheda in Google Chrome: {exe}")
                return
            except Exception as e:
                log(f"Tentativo Chrome fallito: {e}")

    # 2. Fallback su altri browser installati (Brave, Edge, Opera, Firefox)
    for b_type, exe in browsers:
        try:
            subprocess.Popen(
                [exe, url],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            log(f"Aperta scheda in {b_type}: {exe}")
            return
        except Exception:
            continue

    # 3. Fallback universale (browser predefinito di sistema)
    webbrowser.open(url)


# -----------------------------------------------------------------------------
# Interfaccia Grafica di Avvio (Splash Window Tkinter)
# -----------------------------------------------------------------------------
class DossierLexSplash:
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk

        self.root = tk.Tk()
        self.root.title("DossierLex")
        self.root.overrideredirect(True)  # Finestra senza bordi standard

        # Dimensioni e centratura a schermo
        w, h = 440, 230
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.configure(bg="#2D352B")

        # Frame con bordo oro
        self.main_frame = tk.Frame(self.root, bg="#3F4A3C", bd=2, relief="solid", highlightbackground="#C8A55A", highlightthickness=2)
        self.main_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # Header: Titolo
        self.title_lbl = tk.Label(
            self.main_frame,
            text="DossierLex",
            font=("Segoe UI", 22, "bold"),
            fg="#F8FAFC",
            bg="#3F4A3C",
        )
        self.title_lbl.pack(pady=(22, 2))

        # Subtitle: Studio
        self.sub_lbl = tk.Label(
            self.main_frame,
            text="STUDIO LEGALE AVV. AURELIO BENTIVEGNA",
            font=("Segoe UI", 9, "bold"),
            fg="#C8A55A",
            bg="#3F4A3C",
        )
        self.sub_lbl.pack(pady=(0, 20))

        # Status text
        self.status_lbl = tk.Label(
            self.main_frame,
            text="Inizializzazione in corso...",
            font=("Segoe UI", 10),
            fg="#E2E8F0",
            bg="#3F4A3C",
        )
        self.status_lbl.pack(pady=(0, 12))

        # Barra di progresso
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Dossier.Horizontal.TProgressbar", foreground="#C8A55A", background="#C8A55A", troughcolor="#2D352B", bordercolor="#3F4A3C")
        self.prog = ttk.Progressbar(
            self.main_frame,
            style="Dossier.Horizontal.TProgressbar",
            mode="indeterminate",
            length=320,
        )
        self.prog.pack(pady=(0, 10))
        self.prog.start(12)

        # Permetti chiusura con tasto Esc
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    def update_status(self, text: str):
        def _set():
            self.status_lbl.config(text=text)
        self.root.after(0, _set)

    def close(self):
        self.root.after(0, self.root.destroy)


def run_launch_sequence(splash=None):
    """Sequenza reattiva di avvio in thread secondario."""
    try:
        log("Inizio sequenza di avvio DossierLex...")

        # 1. Se l'app e' gia' pronta
        if is_app_ready():
            log("DossierLex e' gia' attivo su porta 3001. Apertura immediata.")
            if splash:
                splash.update_status("DossierLex pronto! Apertura in corso...")
                time.sleep(0.4)
                splash.close()
            open_browser_app(APP_URL)
            return

        # 2. Controllo Docker
        if splash:
            splash.update_status("Verifica motore Docker dello studio...")

        if not is_docker_running():
            log("Docker non in esecuzione. Avvio di Docker Desktop...")
            if splash:
                splash.update_status("Avvio di Docker Desktop in corso...")
            start_docker_desktop()

            # Attesa che Docker sia online (max 40 secondi)
            docker_ready = False
            for sec in range(40):
                time.sleep(1.0)
                if is_docker_running():
                    docker_ready = True
                    log(f"Docker e' diventato operativo dopo {sec+1}s.")
                    break
                if splash and sec % 3 == 0:
                    splash.update_status(f"Inizializzazione motore Docker ({sec+1}s)...")

            if not docker_ready:
                log("Timeout avvio Docker Desktop.")
                if splash:
                    splash.update_status("Avviso: Docker sta impiegando piu' del previsto...")

        # 3. Avvio container DossierLex
        if splash:
            splash.update_status("Avvio servizi DossierLex (DB, AI, Backend)...")
        start_dossierlex_containers()

        # 4. Attesa sincronizzata: il browser si apre SOLO quando sia Backend che Frontend sono al 100% attivi
        ready = False
        for sec in range(50):
            time.sleep(0.8)
            b_ok = is_backend_ready()
            f_ok = is_frontend_ready()
            if b_ok and f_ok:
                ready = True
                log(f"DossierLex e' completamente online (Backend :8000 e Frontend :3001) dopo {sec+1} tentativi.")
                break
            if splash and sec % 3 == 0:
                if not b_ok:
                    splash.update_status("Avvio del database e del backend AI...")
                elif not f_ok:
                    splash.update_status("Avvio interfaccia grafica...")

        if splash:
            if ready:
                splash.update_status("DossierLex pronto! Apertura in corso...")
            else:
                splash.update_status("Accesso all'applicazione in corso...")
            time.sleep(0.5)
            splash.close()

        open_browser_tab(APP_URL)

    except Exception as e:
        log(f"Eccezione durante la sequenza di avvio: {e}")
        if splash:
            splash.update_status("Errore durante l'avvio. Controlla launcher.log")
            time.sleep(2.0)
            splash.close()
        open_browser_tab(APP_URL)


def main():
    log("Launcher avviato.")

    # 1. Se l'app e' gia' pronta, apri all'istante senza splash
    if is_app_ready():
        log("DossierLex e' gia' in esecuzione. Apertura immediata.")
        open_browser_tab(APP_URL)
        return

    # 2. Mostra la splash window mentre avvia Docker e i container
    try:
        splash = DossierLexSplash()
        t = threading.Thread(target=run_launch_sequence, args=(splash,), daemon=True)
        t.start()
        splash.root.mainloop()
    except Exception as e:
        log(f"Tkinter non disponibile o errore splash: {e}. Fallback background puro.")
        run_launch_sequence(splash=None)


if __name__ == "__main__":
    main()

