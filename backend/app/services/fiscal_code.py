"""
Utility per il codice fiscale / partita IVA — la CHIAVE che concatena la pratica.

Il CF (normalizzato) e il "punto fermo" di ogni pratica: serve a riconoscere
con certezza il cliente dentro i documenti (es. quale socio di una camerale e
il titolare) e a far partire le ricerche esterne.

Validazione di FORMATO BASE (scelta di progetto):
- Persona fisica: 16 caratteri alfanumerici.
- Azienda / partita IVA: 11 cifre.
Non verifica il carattere di controllo (validazione formale completa rimandata).
"""
import re


def normalize(cf: str) -> str:
    """Normalizza per confronti affidabili: maiuscolo, senza spazi/punteggiatura."""
    if not cf:
        return ""
    return re.sub(r"[^A-Z0-9]", "", cf.upper())


def is_valid_format(cf: str) -> bool:
    """True se il formato base e plausibile (16 char persona o 11 cifre azienda)."""
    c = normalize(cf)
    if len(c) == 16 and c.isalnum():
        return True
    if len(c) == 11 and c.isdigit():
        return True
    return False


def kind(cf: str) -> str:
    """Ritorna 'persona' (16), 'azienda' (11) o 'sconosciuto'."""
    c = normalize(cf)
    if len(c) == 16:
        return "persona"
    if len(c) == 11:
        return "azienda"
    return "sconosciuto"


def same(cf_a: str, cf_b: str) -> bool:
    """Confronto robusto tra due codici fiscali (normalizzati)."""
    a, b = normalize(cf_a), normalize(cf_b)
    return bool(a) and a == b
