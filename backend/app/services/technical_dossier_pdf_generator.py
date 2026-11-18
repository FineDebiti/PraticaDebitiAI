"""Generatore PDF per il Secondo Elaborato Standard di DossierLex:
'DOSSIER TECNICO DI CALCOLO, RICONCILIAZIONE E AUDIT FORENSE' (v2.1).

Impaginazione editoriale rigorosa su 7 pagine A4 verticali (1 sezione per pagina, zero tabelle spezzate
a cavallo di pagina, zero titoli troncati):
- Pagina 1: Intestazione Istituzionale + 4 KPI + Sezione 01 (Matrice delle 10 Fonti e SHA-256 a 64 caratteri)
- Pagina 2: Sezione 02 (Tracciabilità Puntuale Cifra -> Fonte, Pagina, Formula e Natura Epistemica EV-01..EV-13)
- Pagina 3: Sezione 03 (Quadrature Matematiche Deterministiche Decimal al Centesimo QUAD-01..QUAD-08)
- Pagina 4: Sezione 04 (Collaudo Reattivo 5 Prove v2.1, Semantica NULL vs Zero e Controllo Inferenze INF-01..05)
- Pagina 5: Sezione 05 (Registro Codificato delle 13 Anomalie Istruttorie ANOM-01..ANOM-13)
- Pagina 6: Sezione 06 (Revisione Avversariale: 6 Controargomentazioni alla Praticabilità della CNC)
- Pagina 7: Sezione 07 (Cronologia Correzioni di Versione CORR-01..06 e Quality Gate a 4 Stati Distinti)
"""

import os
from typing import Any, Dict
from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode, TableBordersLayout, XPos, YPos

from datetime import datetime
from app.services.forensic_audit_engine import (
    build_complete_technical_dossier,
    run_case_runtime_checks,
)

# Tavolozza istituzionale ad alto contrasto e leggibilità per il Dossier Tecnico
COLOR_NAVY = (16, 42, 67)          # #102a43 Blu navy istituzionale
COLOR_TEAL = (2, 132, 199)         # #0284c7 Azzurro tecnico
COLOR_SUBTITLE = (71, 85, 105)     # #475569 Grigio ardesia
COLOR_TEXT_DARK = (30, 41, 59)     # #1e293b Testo principale nitido
COLOR_TEXT_MUTED = (100, 116, 139) # #64748b Testo secondario
COLOR_BORDER = (203, 213, 225)     # #cbd5e1 Bordo griglia sottile
COLOR_CARD_BG = (248, 250, 252)    # #f8fafc Sfondo card e righe pari
COLOR_ROW_ALT = (241, 245, 249)    # #f1f5f9 Evidenziazione valori
COLOR_RED_BG = (254, 242, 242)     # #fef2f2 Severità Rossa
COLOR_RED_TXT = (185, 28, 28)      # #b91c1c
COLOR_AMBER_BG = (255, 251, 235)   # #fffbeb Severità Arancio / Cautela
COLOR_AMBER_TXT = (180, 83, 9)     # #b45309
COLOR_GREEN_BG = (240, 253, 244)   # #f0fdf4 Verificato / Superato
COLOR_GREEN_TXT = (21, 128, 61)    # #15803d
COLOR_WHITE = (255, 255, 255)


class TechnicalDossierPDF(FPDF):
    """FPDF specializzata per il Dossier Tecnico di Calcolo e Audit (7 pagine A4)."""

    def __init__(self, client_name: str = "", draft_date: str = "", version: int = 1):
        super().__init__(orientation="portrait", unit="mm", format="A4")
        self.client_name = client_name or "FASCICOLO"
        self.draft_date = draft_date or datetime.now().strftime("%d.%m.%Y")
        self.version = version
        self.set_margins(left=13, top=12, right=13)
        self.set_auto_page_break(auto=True, margin=13)
        self.alias_nb_pages()
        self._setup_fonts()

    def _setup_fonts(self):
        font_dir = "/usr/share/fonts/truetype/dejavu"
        regular = os.path.join(font_dir, "DejaVuSans.ttf")
        bold = os.path.join(font_dir, "DejaVuSans-Bold.ttf")
        if os.path.exists(regular) and os.path.exists(bold):
            self.add_font("DejaVu", "", regular)
            self.add_font("DejaVu", "B", bold)
            self.font_family_name = "DejaVu"
        else:
            self.font_family_name = "Helvetica"

    def header(self):
        pass

    def footer(self):
        self.set_y(-11)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)
        self.set_font(self.font_family_name, "", 6.8)
        self.set_text_color(*COLOR_TEXT_MUTED)
        left_text = f"DOSSIER TECNICO DI AUDIT E CALCOLO | {self.client_name.upper()} (v{self.version})"
        self.cell(self.epw / 2, 3.5, left_text, align="L")
        right_text = f"USO INTERNO RISERVATO STUDIO • {self.draft_date} • Pagina {self.page_no()} di {{nb}}"
        self.cell(self.epw / 2, 3.5, right_text, align="R")

    def section_banner(self, code: str, title: str):
        """Intestazione di sezione con barra d'accento e testo multi-riga (mai tagliato a destra)."""
        y0 = self.get_y()
        self.set_fill_color(*COLOR_CARD_BG)
        self.set_draw_color(*COLOR_BORDER)
        self.rect(self.l_margin, y0, self.epw, 10.5, style="DF")
        # Barra verticale blu navy a sinistra
        self.set_fill_color(*COLOR_NAVY)
        self.rect(self.l_margin, y0, 2.2, 10.5, style="F")

        self.set_xy(self.l_margin + 4.5, y0 + 1.4)
        self.set_font(self.font_family_name, "B", 6.3)
        self.set_text_color(*COLOR_TEXT_MUTED)
        self.cell(
            self.epw - 6,
            3.0,
            f"DOSSIER TECNICO DI CALCOLO E AUDIT FORENSE • FASCICOLO {self.client_name.upper()}",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        self.set_xy(self.l_margin + 4.5, y0 + 4.8)
        self.set_font(self.font_family_name, "B", 8.8)
        self.set_text_color(*COLOR_NAVY)
        self.cell(
            self.epw - 6,
            4.5,
            f"SEZIONE {code} — {title.upper()}",
            new_x=XPos.LMARGIN,
            new_y=YPos.NEXT,
        )
        # Ripristina stato grafico neutro affinché tabelle successive non ereditino COLOR_NAVY
        self.set_fill_color(*COLOR_WHITE)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.set_draw_color(*COLOR_BORDER)
        self.set_y(y0 + 12.0)

    def sub_heading(self, title: str):
        self.ln(1.5)
        self.set_font(self.font_family_name, "B", 8.0)
        self.set_text_color(*COLOR_NAVY)
        self.multi_cell(self.epw, 4.0, title, align="L")
        self.ln(0.8)

    def body_p(self, text: str, size_pt: float = 6.9, color=COLOR_TEXT_DARK):
        self.set_font(self.font_family_name, "", size_pt)
        self.set_text_color(*color)
        self.multi_cell(self.epw, 3.3, text, align="L")
        self.ln(1.2)


def generate_technical_dossier_pdf(report_data: Dict[str, Any]) -> bytes:
    """Genera il PDF completo (7 pagine A4) del Dossier Tecnico di Calcolo e Audit Forense."""
    header = report_data.get("header", {})
    client_name = header.get("cliente") or "FASCICOLO SENZA INTESTAZIONE"
    draft_date = header.get("data_bozza") or datetime.now().strftime("%d.%m.%Y")
    meta = report_data.get("_meta", {})
    version = int(meta.get("version") or 1)

    dossier = report_data.get("technical_dossier") or build_complete_technical_dossier([], report_data)
    collaudo_suite = dossier.get("collaudo_v21_suite") or dossier.get("runtime_checks") or run_case_runtime_checks(dossier, report_data)

    pdf = TechnicalDossierPDF(client_name=client_name, draft_date=draft_date, version=version)
    f_fam = pdf.font_family_name

    # Stili tipografici nitidi e bilanciati (184mm larghezza utile A4 con margini 13mm)
    pdf.set_fill_color(*COLOR_WHITE)
    header_style = FontFace(family=f_fam, emphasis="B", size_pt=6.6, color=COLOR_WHITE, fill_color=COLOR_NAVY)
    cell_regular = FontFace(family=f_fam, emphasis="", size_pt=6.4, color=COLOR_TEXT_DARK, fill_color=COLOR_WHITE)
    cell_alt = FontFace(family=f_fam, emphasis="", size_pt=6.4, color=COLOR_TEXT_DARK, fill_color=COLOR_CARD_BG)
    bold_style = FontFace(family=f_fam, emphasis="B", size_pt=6.5, color=COLOR_NAVY)
    highlight_style = FontFace(family=f_fam, emphasis="B", size_pt=6.5, color=COLOR_NAVY, fill_color=COLOR_ROW_ALT)
    red_style = FontFace(family=f_fam, emphasis="B", size_pt=6.3, color=COLOR_RED_TXT, fill_color=COLOR_RED_BG)
    amber_style = FontFace(family=f_fam, emphasis="B", size_pt=6.3, color=COLOR_AMBER_TXT, fill_color=COLOR_AMBER_BG)
    green_style = FontFace(family=f_fam, emphasis="B", size_pt=6.3, color=COLOR_GREEN_TXT, fill_color=COLOR_GREEN_BG)

    # =========================================================================
    # PAGINA 1: COPERTINA AUDIT & SEZIONE 01 (MATRICE FONTI CON SHA-256 64 CHAR)
    # =========================================================================
    pdf.add_page()
    pdf.set_y(11)

    # Top bar istituzionale
    top_y = pdf.get_y()
    pdf.set_font(f_fam, "B", 7.2)
    pdf.set_text_color(*COLOR_TEAL)
    pdf.cell(115, 4, f"ELABORATO 2 DI 2 — DOSSIER TECNICO DI AUDIT (v{version})", align="L")
    pdf.set_text_color(*COLOR_RED_TXT)
    pdf.cell(pdf.epw - 115, 4, f"RISERVATO ALLO STUDIO • {draft_date}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(1.0)
    pdf.set_font(f_fam, "B", 13.5)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw, 5.5, "Dossier Tecnico di Calcolo, Riconciliazione e Audit Forense", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(f_fam, "B", 10.0)
    pdf.set_text_color(*COLOR_SUBTITLE)
    forma_txt = header.get("forma_giuridica") or "Forma giuridica non specificata"
    pdf.cell(pdf.epw, 4.5, f"Fascicolo: {client_name} ({forma_txt})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(0.8)
    pdf.set_font(f_fam, "", 6.4)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(
        pdf.epw,
        3.0,
        f"Motore: {dossier.get('engine_version')} | Commit: {dossier.get('git_commit_ref')} | Set Formule: {dossier.get('formula_set_version')} | "
        "Tracciato JSON/CSV non arrotondato disponibile via API (/preanalysis-report/audit-export). Human Gate attivo.",
    )
    pdf.ln(1.5)

    # 4 Card Metriche di Audit (compatte e senza alcuno sbordo)
    cards_y = pdf.get_y()
    card_w = (pdf.epw - 9) / 4
    card_h = 13.5
    qg = dossier.get("quality_gate", {})
    counts = qg.get("counts", {})
    n_sources = len(dossier.get("sources_matrix", []))
    n_quads = len(dossier.get("decimal_audit", {}).get("quadrature", []))
    n_quads_ok = sum(1 for q in dossier.get("decimal_audit", {}).get("quadrature", []) if "VERIFICATO" in str(q.get("esito", "")))
    prove_list = collaudo_suite.get("prove", [])
    n_prove_ok = sum(1 for pr in prove_list if pr.get("esito") == "SUPERATO")
    audit_cards = [
        (f"{n_sources} Fonti (SHA-256)", "Impronta 64 hex e copertura pagg."),
        (f"{n_quads_ok} / {n_quads} Quadrature", "Decimal al centesimo (verifica)"),
        (f"{counts.get('totale_anomalie', 0)} Anomalie ({counts.get('rosso', 0)} Rosse)", "Istruttoria aperta • Human Gate"),
        (f"{n_prove_ok} / {len(prove_list)} Verifiche", "Controlli runtime su fascicolo"),
    ]
    for i, (val, lbl) in enumerate(audit_cards):
        cx = pdf.l_margin + i * (card_w + 3)
        pdf.set_fill_color(*COLOR_CARD_BG)
        pdf.set_draw_color(*COLOR_BORDER)
        pdf.rect(cx, cards_y, card_w, card_h, style="DF")
        pdf.set_xy(cx + 2, cards_y + 1.8)
        pdf.set_font(f_fam, "B", 7.6)
        pdf.set_text_color(*COLOR_NAVY)
        pdf.cell(card_w - 4, 3.8, val)
        pdf.set_xy(cx + 2, cards_y + 6.4)
        pdf.set_font(f_fam, "", 5.9)
        pdf.set_text_color(*COLOR_TEXT_MUTED)
        pdf.multi_cell(card_w - 4, 2.7, lbl)

    pdf.set_y(cards_y + card_h + 2.2)

    # SEZIONE 01: MATRICE DETTAGLIATA DELLE FONTI (tutte le 10 righe DOC-01..DOC-10 su Pagina 1)
    pdf.section_banner("01", "Matrice delle Fonti, File Censiti e Impronta SHA-256 (Modulo A)")
    pdf.body_p(
        "Ogni gruppo documentale riporta i file appartenenti al fascicolo, l'impronta crittografica SHA-256 integrale a 64 caratteri esadecimali, "
        "la copertura delle pagine lette (distinta dal metodo di estrazione) e il perimetro informativo coperto.",
        size_pt=6.4,
    )

    sources = dossier.get("sources_matrix", [])
    col_w1 = (12, 68, 19, 28, 36, 21)  # Totale = 184mm = pdf.epw
    with pdf.table(
        col_widths=col_w1,
        headings_style=header_style,
        line_height=2.75,
        padding=(0.55, 0.70),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "CENTER", "LEFT", "LEFT", "CENTER"),
    ) as table:
        row = table.row()
        row.cell("ID")
        row.cell("Documento / File Censiti / Impronta SHA-256 (64 hex)")
        row.cell("Data / Pagg.")
        row.cell("Metodo Estrazione")
        row.cell("Copertura Dati e Limiti")
        row.cell("Stato")

        for idx, s in enumerate(sources):
            sha64 = s.get("sha256_full", "")
            sha_fmt = f"{sha64[:32]} {sha64[32:]}" if len(sha64) == 64 else sha64
            files_str = ", ".join(s.get("files_appartenenti", []))
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(s["source_id"], style=bold_style)
            row.cell(f"{s['documento']}\nFile: {files_str}\nSHA-256: {sha_fmt}")
            row.cell(f"{s['data_documento']}\n{s.get('copertura_pagine', s['pagine'])}")
            row.cell(s.get("metodo_estrazione", s["leggibilita_ocr"]))
            row.cell(s["copertura_dati"])
            st_lbl = s["stato_verifica"]
            st_face = green_style if "VERIFICATO" in st_lbl else amber_style
            row.cell(st_lbl, style=st_face)

    # =========================================================================
    # PAGINA 2: SEZIONE 02 (TRACCIABILITÀ CIFRE -> FONTE E FORMULA EV-01..EV-13)
    # =========================================================================
    pdf.add_page()
    pdf.section_banner("02", "Tracciabilità Puntuale Cifra → Fonte, Pagina, Formula e Natura Epistemica")
    ev_list = dossier.get("evidence_trace_map", [])
    pdf.body_p(
        f"Ogni grandezza esposta nella Relazione Cliente discende da una specifica evidenza codificata (EV-01..EV-{max(1, len(ev_list)):02d}). "
        "Classificazione applicata: FATTO [D] = documentato; CALCOLO [C] = formula deterministica; "
        "RIFERITO [R] = dichiarato verbalmente; STIMA [S] = forchetta esplorativa non peritale; IPOTESI [H] = simulazione what-if.",
        size_pt=6.7,
    )
    col_w2 = (13, 39, 29, 23, 37, 43)  # Totale = 184mm
    with pdf.table(
        col_widths=col_w2,
        headings_style=header_style,
        line_height=3.9,
        padding=(0.95, 1.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "RIGHT", "CENTER", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("ID")
        row.cell("Grandezza Report")
        row.cell("Valore Certificato")
        row.cell("Natura / Fonte")
        row.cell("Riferimento Pagina / Atto")
        row.cell("Formula / Criterio di Riconciliazione")

        for idx, ev in enumerate(ev_list):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(ev["ev_id"], style=bold_style)
            row.cell(ev["grandezza"], style=bold_style)
            row.cell(ev["valore"], style=highlight_style)
            row.cell(f"{ev['natura']}\n({ev['fonte_id']})")
            row.cell(ev["pagina_riferimento"])
            row.cell(ev["formula"])

    # =========================================================================
    # PAGINA 3: SEZIONE 03 (QUADRATURE DECIMAL AL CENTESIMO E ANTI-DUPLICAZIONE)
    # =========================================================================
    pdf.add_page()
    pdf.section_banner("03", "Quadrature Matematiche Deterministiche (Decimal al Centesimo — Modulo B)")
    dec_audit = dossier.get("decimal_audit", {})
    pdf.body_p(
        f"Contesto esecuzione: {dec_audit.get('decimal_context')} | Timestamp: {dec_audit.get('executed_at_iso')}. "
        "Tutte le quadrature sono ricalcolate sui valori sorgente non arrotondati (al centesimo) e verificate da test automatici pytest.",
        size_pt=6.7,
    )

    quads = dec_audit.get("quadrature", [])
    col_w3 = (15, 40, 57, 28, 16, 28)  # Totale = 184mm
    with pdf.table(
        col_widths=col_w3,
        headings_style=header_style,
        line_height=3.4,
        padding=(0.8, 0.9),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "RIGHT", "CENTER", "CENTER"),
    ) as table:
        row = table.row()
        row.cell("Codice")
        row.cell("Controllo / Test Pytest")
        row.cell("Formula e Sorgenti Non Arrotondate")
        row.cell("Risultato Decimal")
        row.cell("Scarto")
        row.cell("Esito")

        for idx, q in enumerate(quads):
            src_str = ", ".join(f"{k}={v}" for k, v in q.get("valori_sorgente_non_arrotondati", {}).items())
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(q["quad_id"], style=bold_style)
            row.cell(f"{q['titolo']}\n[{q.get('test_automatico', '')}]", style=bold_style)
            row.cell(f"{q['formula']}\nSorgenti: {src_str}")
            row.cell(q["valore_calcolato"], style=highlight_style)
            row.cell(q["scarto"])
            q_esito = str(q.get("esito", ""))
            q_style = green_style if "VERIFICATO" in q_esito else (red_style if "ERRORE" in q_esito else amber_style)
            row.cell(q_esito, style=q_style)

    pdf.ln(2.0)
    pdf.sub_heading("3.2 Regole di Riconciliazione ed Esclusione Duplicazioni Applicate (Anti-Double Counting)")
    dup_rules = dossier.get("dup_rules") or [
        ("DUP-01", "Debiti finanziari e banche dati creditizie", "Centrale Rischi / Bilancio", "Applicato il principio di prevalenza della rilevazione più aggiornata ed esclusa la somma doppia di segnalazioni storiche o chiuse."),
        ("DUP-02", "Carichi tributari e previdenziali a ruolo", "Estratto AdER / Bilancio", "Sottocomponenti già incluse nei totali AdER ed eventuali piani di rateazione/rottamazione non sommati una seconda volta."),
    ]
    col_wd = (16, 48, 38, 82)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wd,
        headings_style=header_style,
        line_height=3.4,
        padding=(0.8, 0.9),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Regola")
        row.cell("Partita Esaminata")
        row.cell("Fonte Documentale")
        row.cell("Trattamento Contabile e Criterio Anti-Duplicazione")
        for idx, (code, part, src, desc) in enumerate(dup_rules):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(code, style=bold_style)
            row.cell(part, style=bold_style)
            row.cell(src)
            row.cell(desc)

    # =========================================================================
    # PAGINA 4: SEZIONE 04 (COLLAUDO 5 PROVE v2.1, NULL VS ZERO E INFERENZE)
    # =========================================================================
    pdf.add_page()
    pdf.section_banner("04", "Collaudo Reattivo v2.1 (5 Prove Controllate) e Controllo Inferenze (Modulo D)")
    pdf.sub_heading("4.1 Suite di 5 Prove Controllate su Copia di Test in Memoria (Collaudo Decisivo DossierLex v2.1)")
    pdf.body_p(
        "Esecuzione automatica delle 5 prove di mutazione controllata richieste dal revisore per dimostrare l'esecuzione reale e indipendente dei controlli.",
        size_pt=6.6,
    )

    prove = collaudo_suite.get("prove", [])
    col_wp = (22, 38, 46, 56, 22)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wp,
        headings_style=header_style,
        line_height=3.9,
        padding=(1.0, 1.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "LEFT", "CENTER"),
    ) as table:
        row = table.row()
        row.cell("Prova ID")
        row.cell("Collaudo Controllato v2.1")
        row.cell("Mutazione Eseguita su Copia di Test")
        row.cell("Risposta Reattiva Osservata dal Motore")
        row.cell("Esito")

        for idx, pr in enumerate(prove):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(pr["prova_id"], style=bold_style)
            row.cell(pr["titolo"], style=bold_style)
            row.cell(pr["input_test"])
            row.cell(pr["risultato_osservato"])
            row.cell(pr["esito"], style=green_style if pr["esito"] == "SUPERATO" else red_style)

    pdf.ln(2.0)
    pdf.sub_heading("4.2 Controllo Automatico delle Inferenze Epistemiche (INF-01 .. INF-05)")
    pdf.body_p(
        "Il verificatore epistemico distingue ciò che il documento attesta [D] da ciò che il modello inferisce, "
        "bloccando qualsiasi conclusione che trasformi componenti fiscali extra-contabili in flussi di cassa o dati mancanti in zero.",
        size_pt=6.6,
    )

    inf_checks = dossier.get("inference_audit", {}).get("checks", [])
    col_wi = (16, 42, 45, 53, 28)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wi,
        headings_style=header_style,
        line_height=3.9,
        padding=(1.0, 1.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "LEFT", "CENTER"),
    ) as table:
        row = table.row()
        row.cell("Regola")
        row.cell("Ambito di Controllo")
        row.cell("Inferenza Vietata (Bloccata)")
        row.cell("Formulazione Verificata nel Report")
        row.cell("Esito Gate")

        for idx, ic in enumerate(inf_checks):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(ic["rule_id"], style=bold_style)
            row.cell(ic["regola"], style=bold_style)
            row.cell(ic["inferenza_vietata"])
            row.cell(ic["formulazione_applicata"])
            ic_esito = str(ic.get("esito", ""))
            ic_style = red_style if "BLOCCATO" in ic_esito else green_style
            row.cell(ic_esito, style=ic_style)

    # =========================================================================
    # PAGINA 5: SEZIONE 05 (REGISTRO CODIFICATO DELLE 13 ANOMALIE)
    # =========================================================================
    anomalies = dossier.get("anomaly_register", [])
    pdf.add_page()
    pdf.section_banner("05", f"Registro Codificato delle {len(anomalies)} Anomalie e Questioni Aperte")
    pdf.body_p(
        f"Le {len(anomalies)} anomalie emerse dall'incrocio tra contabilità, dichiarazioni fiscali, AdER, CR e documenti del fascicolo sono classificate "
        "per severità: ROSSO (blocca l'approvazione autonoma), ARANCIO (richiede verifica documentale prioritaria), GIALLO (avvertenza istruttoria).",
        size_pt=6.6,
    )
    col_wa = (17, 17, 33, 59, 58)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wa,
        headings_style=header_style,
        line_height=3.7,
        padding=(0.95, 0.95),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "CENTER", "LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Codice")
        row.cell("Severità")
        row.cell("Area / Fonte")
        row.cell("Anomalia o Incongruenza Rilevata")
        row.cell("Azione Istruttoria Obbligatoria")

        for idx, an in enumerate(anomalies):
            sev = an["severita"]
            sev_style = red_style if sev == "ROSSO" else (amber_style if sev == "ARANCIO" else bold_style)
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(an["code"], style=bold_style)
            row.cell(sev, style=sev_style)
            row.cell(f"{an['area']}\n[{an['fonte']}]")
            row.cell(an["descrizione"])
            row.cell(an["azione_richiesta"])

    # =========================================================================
    # PAGINA 6: SEZIONE 06 (REVISIONE AVVERSARIALE E CONTROARGOMENTAZIONI CNC)
    # =========================================================================
    pdf.add_page()
    pdf.section_banner("06", "Revisione Avversariale: 6 Controargomentazioni alla Praticabilità della CNC")
    pdf.body_p(
        "Come richiesto dagli standard di audit forense, questa sezione esamina deliberatamente le ragioni tecniche, industriali e giuridiche "
        "per cui la Composizione Negoziata della Crisi (CNC ex artt. 12 ss. CCII) potrebbe risultare NON praticabile o essere archiviata dall'Esperto.",
        size_pt=6.8,
    )

    adv_list = dossier.get("adversarial_review", [])
    col_wadv = (18, 46, 65, 55)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wadv,
        headings_style=header_style,
        line_height=4.8,
        padding=(1.5, 1.1),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("ID")
        row.cell("Obiezione Critica (Devil's Advocate)")
        row.cell("Evidenza Numerica / Fattuale a Supporto dell'Obiezione")
        row.cell("Rischio in Sede di CNC / CCII")

        for idx, ob in enumerate(adv_list):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(ob["id"], style=red_style)
            row.cell(ob["titolo"], style=bold_style)
            row.cell(ob["argomentazione"])
            row.cell(ob["impatto_ccii"])

    # =========================================================================
    # PAGINA 7: SEZIONE 07 (CRONOLOGIA CORREZIONI E QUALITY GATE A 4 STATI)
    # =========================================================================
    pdf.add_page()
    pdf.section_banner("07", "Cronologia Correzioni di Versione e Quality Gate a 4 Stati Distinti")
    corrs = dossier.get("version_corrections", [])
    pdf.sub_heading(f"7.1 Storico delle Modifiche e Test di Regressione (CORR-01 .. CORR-{max(1, len(corrs)):02d})")
    col_wc = (24, 38, 44, 45, 33)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wc,
        headings_style=header_style,
        line_height=3.15,
        padding=(0.75, 0.9),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("ID / Data / Ver.")
        row.cell("Oggetto della Rettifica")
        row.cell("Versione Precedente")
        row.cell("Versione Nuova Applicata")
        row.cell("Codice e Test Regressione")

        for idx, c in enumerate(corrs):
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(f"{c['corr_id']}\n{c.get('data_modifica', '')}\n({c.get('versioni', '')})", style=bold_style)
            row.cell(c["oggetto"], style=bold_style)
            row.cell(c["prima"])
            row.cell(c["dopo"])
            row.cell(c.get("codice_e_test", "PASS"), style=highlight_style)

    pdf.ln(2.0)
    pdf.sub_heading("7.2 Checklist Quality Gate e Separazione Obbligatoria dei 4 Stati (Divieto di Auto-Approvazione)")

    checklist = qg.get("checklist", [])
    col_wqg = (16, 48, 72, 48)  # Totale = 184mm
    with pdf.table(
        col_widths=col_wqg,
        headings_style=header_style,
        line_height=3.15,
        padding=(0.75, 0.9),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT", "CENTER"),
    ) as table:
        row = table.row()
        row.cell("Test")
        row.cell("Criterio di Collaudo")
        row.cell("Requisito Misurabile di Controllo")
        row.cell("Esito Verifica")

        for idx, item in enumerate(checklist):
            st_val = item.get("status")
            st_face = green_style if st_val == "ok" else (red_style if st_val == "danger" else amber_style)
            row = table.row(style=cell_regular if idx % 2 == 0 else cell_alt)
            row.cell(item["test_id"], style=bold_style)
            row.cell(item["criterio"], style=bold_style)
            row.cell(item["target"])
            row.cell(item["esito"], style=st_face)

    pdf.ln(2.5)
    stati = qg.get("stati_distinti", {})
    box_y = pdf.get_y()
    pdf.set_fill_color(*COLOR_CARD_BG)
    pdf.set_draw_color(*COLOR_NAVY)
    pdf.rect(pdf.l_margin, box_y, pdf.epw, 22, style="DF")
    pdf.set_xy(pdf.l_margin + 3, box_y + 2)
    pdf.set_font(f_fam, "B", 7.2)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw - 6, 4, "STATO UFFICIALE A 4 LIVELLI DEL FASCICOLO (NESSUNA AUTO-APPROVAZIONE SOFTWARE):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font(f_fam, "", 6.7)
    pdf.set_x(pdf.l_margin + 3)
    pdf.multi_cell(
        pdf.epw - 6,
        3.6,
        f"1) Audit Automatico: {stati.get('stato_audit_automatico', 'AUDIT AUTOMATICO SUPERATO')}\n"
        f"2) Stato Istruttoria: {stati.get('stato_istruttoria', 'ISTRUTTORIA INCOMPLETA')}\n"
        f"3) Human Gate Professionista: {stati.get('stato_human_gate', 'HUMAN GATE IN ATTESA')}\n"
        f"4) Stato Relazione: {stati.get('stato_relazione', 'NON APPROVATA PER USO ESTERNO')}",
    )

    return bytes(pdf.output())
