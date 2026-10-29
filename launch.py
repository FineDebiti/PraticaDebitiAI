"""
DossierLex - Launcher Desktop Universale e Silenzioso
Studio Legale Avv. Aurelio Bentivegna

Supporta tutti i browser: Chrome, Brave, Edge, Opera, Safari, Firefox.
Avvia Docker in modalita' 100% invisibile se non e' gia' attivo.
"""
import os
import sys
import time
import subprocess
import urllib.request
import urllib.error
import webbrowser

PORT = 3001
URL = f"http://127.0.0.1:{PORT}"
HEALTH_URL = "http://127.0.0.1:8000/api/health"

CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def is_service_ready():
    """Verifica se il frontend o il backend rispondono su porta 3001 o 8000."""
    try:
        with urllib.request.urlopen(URL, timeout=1.5) as res:
            if res.status in (200, 304):
                return True
    except Exception:
        pass
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=1.5) as res:
            if res.status == 200:
                return True
    except Exception:
        pass
    return False


def start_docker_containers():
    """Avvia i container di DossierLex in background senza alcuna finestra nera."""
    if sys.platform == "win32":
        # Avvio tramite WSL2 in background senza finestra
        wsl_cmd = (
            "wsl -e bash -lc "
            "\"cd /home/giuseppe/PraticaDebitiAI && "
            "docker compose -f docker-compose.local.yml up -d\""
        )
        try:
            subprocess.Popen(
                wsl_cmd,
                shell=True,
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

        # Fallback se docker compose e' disponibile direttamente in Windows
        try:
            subprocess.Popen(
                ["docker", "compose", "-f", "docker-compose.local.yml", "up", "-d"],
                creationflags=CREATE_NO_WINDOW,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    elif sys.platform == "darwin":
        # macOS
        try:
            subprocess.Popen(
                ["docker", "compose", "-f", "docker-compose.local.yml", "up", "-d"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
    else:
        # Linux
        try:
            subprocess.Popen(
                ["docker", "compose", "-f", "docker-compose.local.yml", "up", "-d"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def get_windows_browsers():
    """Ritorna l'elenco dei browser installati su Windows in ordine di preferenza."""
    local_app_data = os.environ.get("LocalAppData", "")
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

    candidates = [
        # 1. Google Chrome
        os.path.join(prog_files, r"Google\Chrome\Application\chrome.exe"),
        os.path.join(prog_files_x86, r"Google\Chrome\Application\chrome.exe"),
        os.path.join(local_app_data, r"Google\Chrome\Application\chrome.exe"),
        # 2. Brave Browser
        os.path.join(prog_files, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(prog_files_x86, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.join(local_app_data, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
        # 3. Microsoft Edge
        os.path.join(prog_files_x86, r"Microsoft\Edge\Application\msedge.exe"),
        os.path.join(prog_files, r"Microsoft\Edge\Application\msedge.exe"),
        # 4. Opera / Opera GX
        os.path.join(local_app_data, r"Programs\Opera\launcher.exe"),
        os.path.join(local_app_data, r"Programs\Opera GX\launcher.exe"),
        os.path.join(prog_files, r"Opera\launcher.exe"),
    ]

    installed = []
    for path in candidates:
        if path and os.path.isfile(path) and path not in installed:
            installed.append(path)
    return installed


def open_dossierlex_browser(url):
    """Apre DossierLex nel browser preferito (modalita' app o scheda dedicata)."""
    if sys.platform == "win32":
        browsers = get_windows_browsers()
        for b_exe in browsers:
            try:
                # Prova prima con modalita' app (finestra pulita senza barra degli indirizzi)
                subprocess.Popen([b_exe, f"--app={url}"])
                return
            except Exception:
                try:
                    # Fallback finestra normale
                    subprocess.Popen([b_exe, url])
                    return
                except Exception:
                    continue

    elif sys.platform == "darwin":
        # Su macOS apre con 'open' che usa il browser predefinito (Safari, Chrome Mac, ecc.)
        try:
            subprocess.Popen(["open", url])
            return
        except Exception:
            pass

    # Fallback universale (qualsiasi OS e browser predefinito)
    webbrowser.open(url)


def main():
    # 1. Se il servizio non e' ancora attivo, avvia Docker
    if not is_service_ready():
        start_docker_containers()
        # Attesa reattiva: controlla ogni 500ms fino a un massimo di 25 secondi
        for _ in range(50):
            time.sleep(0.5)
            if is_service_ready():
                break

    # 2. Apri DossierLex nel browser
    open_dossierlex_browser(URL)


if __name__ == "__main__":
    main()
