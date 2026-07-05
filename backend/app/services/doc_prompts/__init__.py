"""Pacchetto dei prompt di estrazione, UN FILE PER TIPO DI DOCUMENTO.

Come aggiungere un nuovo documento mappato:
  1. crea un file qui dentro, es. visura_camerale.py, con dentro la costante
     VISURA_CAMERALE_PROMPT = \"\"\"...\"\"\"
  2. importalo qui sotto e aggiungi una riga al dizionario EXTRACT_PROMPTS.
Niente altro da toccare nel resto del codice.

Cosi, se un documento ha problemi, si lavora SOLO sul suo file.
"""
from app.services.doc_prompts.common import CLASSIFY_PROMPT, _COMMON_RULES
from app.services.doc_prompts.generic import GENERIC_EXTRACT_PROMPT
from app.services.doc_prompts.visura_catastale import VISURA_CATASTALE_PROMPT
from app.services.doc_prompts.visura_camerale import VISURA_CAMERALE_PROMPT
from app.services.doc_prompts.centrale_rischi import CENTRALE_RISCHI_PROMPT
from app.services.doc_prompts.bilancio import BILANCIO_PROMPT
from app.services.doc_prompts.cartella_aer import CARTELLA_AER_PROMPT
from app.services.doc_prompts.busta_paga import BUSTA_PAGA_PROMPT
from app.services.doc_prompts.cu import CU_PROMPT
from app.services.doc_prompts.isee import ISEE_PROMPT
from app.services.doc_prompts.estratto_conto import ESTRATTO_CONTO_PROMPT
from app.services.doc_prompts.dichiarazione_redditi import DICHIARAZIONE_REDDITI_PROMPT

# Elenco dei tipi riconosciuti dal classificatore.
DOC_TYPES = [
    "visura_catastale", "visura_camerale", "bilancio",
    "centrale_rischi", "crif", "cartella_aer", "contratto_finanziamento",
    "busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi",
    "pignoramento", "altro",
]

# Registro: tipo documento -> prompt dedicato.
EXTRACT_PROMPTS = {
    "visura_catastale": VISURA_CATASTALE_PROMPT,
    "visura_camerale": VISURA_CAMERALE_PROMPT,
    "centrale_rischi": CENTRALE_RISCHI_PROMPT,
    "bilancio": BILANCIO_PROMPT,
    "cartella_aer": CARTELLA_AER_PROMPT,
    "busta_paga": BUSTA_PAGA_PROMPT,
    "cu": CU_PROMPT,
    "isee": ISEE_PROMPT,
    "estratto_conto": ESTRATTO_CONTO_PROMPT,
    "dichiarazione_redditi": DICHIARAZIONE_REDDITI_PROMPT,
}


def get_extract_prompt(doc_type: str) -> str:
    """Ritorna il prompt dedicato per il tipo, o quello generico se non mappato."""
    return EXTRACT_PROMPTS.get(doc_type, GENERIC_EXTRACT_PROMPT)


# Compatibilita all'indietro.
EXTRACT_PROMPT = GENERIC_EXTRACT_PROMPT
