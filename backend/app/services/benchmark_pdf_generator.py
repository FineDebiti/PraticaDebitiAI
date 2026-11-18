"""Generatore PDF di Preanalisi a 7 Pagine (DossierLex).

Generatore vettoriale A4 unificato e dinamico per tutte le pratiche (ditte individuali,
persone fisiche, S.r.l., S.p.A., società di persone), senza dati preimpostati.
"""

import os
from typing import Dict, Any, List, Optional
from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode, TableBordersLayout, XPos, YPos

# Tavolozza peritale DossierLex Benchmark
COLOR_NAVY = (16, 42, 67)          # #102a43 Titoli e intestazioni primarie
COLOR_TEAL = (2, 132, 199)         # #0284c7 Capitoli (01 / PROFILO...)
COLOR_SUBTITLE = (71, 85, 105)     # #475569 Sottotitoli
COLOR_TEXT_DARK = (30, 41, 59)     # #1e293b Testo principale ad alto contrasto
COLOR_TEXT_MUTED = (100, 116, 139) # #64748b Testo secondario e note
COLOR_BORDER = (203, 213, 225)     # #cbd5e1 Bordi tabelle e card
COLOR_CARD_BG = (248, 250, 252)    # #f8fafc Sfondo card e righe pari
COLOR_ROW_ALT = (241, 245, 249)    # #f1f5f9 Righe evidenziate
COLOR_WHITE = (255, 255, 255)


def _fmt_eur(v) -> str:
    if v is None:
        return "n.d. (NULL)"
    try:
        n = float(v)
        return f"€ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


def _fmt_int(v) -> str:
    if v is None:
        return "—"
    try:
        n = round(float(v))
        return f"{n:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(v)


class BenchmarkPreanalysisPDF(FPDF):
    """FPDF specializzata per il report cliente a 7 pagine esatte senza spazi vuoti residui."""

    def __init__(self, client_name: str = "", draft_date: str = "09.11.2026"):
        super().__init__(orientation="portrait", unit="mm", format="A4")
        self.client_name = client_name or "CLIENTE"
        self.draft_date = draft_date or "09.11.2026"
        self.set_margins(left=15, top=14, right=15)
        self.set_auto_page_break(auto=False)
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
        self.set_y(-13)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.25)
        self.line(self.l_margin, self.get_y() - 1.2, self.w - self.r_margin, self.get_y() - 1.2)
        self.set_font(self.font_family_name, "", 7.8)
        self.set_text_color(*COLOR_TEXT_MUTED)

        left_text = f"PRE-ANALISI CRISI D'IMPRESA | {self.client_name.upper()}"
        self.cell(self.epw / 2, 4.5, left_text, align="L")

        right_text = f"RISERVATO • {self.draft_date} • {self.page_no()} / {{nb}}"
        self.cell(self.epw / 2, 4.5, right_text, align="R")

    def page_top_breadcrumb(self, chapter_code: str, chapter_title: str):
        """Intestazione editoriale standard per le pagine 2-7."""
        self.set_xy(15, 14)
        self.set_font(self.font_family_name, "B", 7.8)
        self.set_text_color(*COLOR_TEXT_MUTED)
        self.cell(self.epw, 4.2, "RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(1.0)
        self.set_font(self.font_family_name, "B", 12.8)
        self.set_text_color(*COLOR_TEAL)
        self.cell(self.epw, 6.2, f"{chapter_code} / {chapter_title.upper()}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(1.5)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.3)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4.0)

    def section_title(self, title: str, top_gap: float = 1.5):
        """Titolo di sezione con barra d'accento verticale."""
        if top_gap > 0:
            self.ln(top_gap)
        y0 = self.get_y()
        self.set_fill_color(*COLOR_TEAL)
        self.rect(self.l_margin, y0 + 0.5, 1.4, 4.5, style="F")
        self.set_fill_color(*COLOR_WHITE)
        self.set_xy(self.l_margin + 3.2, y0)
        self.set_font(self.font_family_name, "B", 10.6)
        self.set_text_color(*COLOR_NAVY)
        self.cell(self.epw - 3.2, 5.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.8)

    def body_p(self, text: str, line_height: float = 4.9, size_pt: float = 9.2, color=COLOR_TEXT_DARK, gap_after: float = 2.6):
        self.set_font(self.font_family_name, "", size_pt)
        self.set_text_color(*color)
        self.multi_cell(self.epw, line_height, text, align="L")
        if gap_after > 0:
            self.ln(gap_after)

    def bullet(self, bold_prefix: str, text: str, line_height: float = 4.7, size_pt: float = 9.0, gap_after: float = 2.1):
        self.set_font(self.font_family_name, "B", size_pt)
        self.set_text_color(*COLOR_NAVY)
        prefix = f"•  {bold_prefix} " if bold_prefix else "•  "
        self.write(line_height, prefix)

        self.set_font(self.font_family_name, "", size_pt)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.write(line_height, text)
        self.ln(line_height + gap_after)

    def framed_box(
        self,
        title: str,
        body: str,
        title_size: float = 8.8,
        body_size: float = 8.6,
        line_height: float = 4.4,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x: float = 4.0,
        pad_y: float = 3.2,
    ):
        """Riquadro informativo auto-dimensionato con barra laterale istituzionale."""
        y0 = self.get_y()
        inner_w = self.epw - (pad_x * 2) - 1.5
        self.set_font(self.font_family_name, "", body_size)
        lines = self.multi_cell(inner_w, line_height, body, dry_run=True, output="LINES")
        title_h = 5.0 if title else 0.0
        box_h = (pad_y * 2) + title_h + (len(lines) * line_height) + 0.5

        self.set_fill_color(*bg_color)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.25)
        self.rect(self.l_margin, y0, self.epw, box_h, style="DF")

        self.set_fill_color(*accent_color)
        self.rect(self.l_margin, y0, 1.8, box_h, style="F")

        curr_y = y0 + pad_y
        if title:
            self.set_xy(self.l_margin + pad_x + 1.0, curr_y)
            self.set_font(self.font_family_name, "B", title_size)
            self.set_text_color(*accent_color)
            self.cell(inner_w, 4.4, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            curr_y += title_h

        self.set_xy(self.l_margin + pad_x + 1.0, curr_y)
        self.set_font(self.font_family_name, "", body_size)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.multi_cell(inner_w, line_height, body, align="L")

        self.set_fill_color(*COLOR_WHITE)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.set_draw_color(*COLOR_BORDER)
        self.set_y(y0 + box_h + 3.0)


def generate_benchmark_7page_pdf(report_data: Dict[str, Any]) -> bytes:
    """Costruisce il PDF dinamico a 7 pagine A4 per qualsiasi azienda o persona fisica (motore unico)."""
    return _generate_dynamic_7page_pdf(report_data)


def _generate_dynamic_7page_pdf(report_data: Dict[str, Any]) -> bytes:
    """Generatore dinamico a 7 pagine A4 per qualsiasi azienda (S.r.l., S.p.A., ditta individuale, persona fisica)."""
    header = report_data.get("header", {})
    c1 = report_data.get("capitolo_1_premessa", {})
    c2 = report_data.get("capitolo_2_profilo", {})
    c3 = report_data.get("capitolo_3_analisi_economica", {})
    c4 = report_data.get("capitolo_4_dato_corrente", {})
    c5 = report_data.get("capitolo_5_indebitamento", {})
    c6 = report_data.get("capitolo_6_punti_verificare", []) or []
    c7 = report_data.get("capitolo_7_diagnosi_crisi", {})
    c8 = report_data.get("capitolo_8_patrimonio", {})
    c9 = report_data.get("capitolo_9_orientamento_risanamento", {})
    c10 = report_data.get("capitolo_10_documentazione", {})
    c11 = report_data.get("capitolo_11_conclusione", {})
    fp = report_data.get("forensic_preanalysis", {})

    from datetime import datetime as _dt
    client_name = header.get("cliente") or "FASCICOLO SENZA INTESTAZIONE"
    draft_date = header.get("data_bozza") or _dt.now().strftime("%d/%m/%Y")
    forma_giuridica = header.get("forma_giuridica") or c2.get("forma_giuridica") or "Forma giuridica non specificata"
    is_srl = any(tok in f"{forma_giuridica} {client_name}".lower() for tok in ("s.r.l", "srl", "s.p.a", "spa", "responsabilita' limitata", "responsabilità limitata"))
    if c2.get("is_ditta_individuale") is True:
        is_srl = False

    pdf = BenchmarkPreanalysisPDF(client_name=client_name, draft_date=draft_date)
    f_fam = pdf.font_family_name

    header_style = FontFace(family=f_fam, emphasis="B", size_pt=7.8, color=COLOR_WHITE, fill_color=COLOR_NAVY)
    cell_white = FontFace(family=f_fam, emphasis="", size_pt=7.8, color=COLOR_TEXT_DARK, fill_color=COLOR_WHITE)
    cell_alt = FontFace(family=f_fam, emphasis="", size_pt=7.8, color=COLOR_TEXT_DARK, fill_color=COLOR_CARD_BG)
    bold_style = FontFace(family=f_fam, emphasis="B", size_pt=7.8, color=COLOR_NAVY)
    highlight_style = FontFace(family=f_fam, emphasis="B", size_pt=7.9, color=COLOR_NAVY, fill_color=COLOR_ROW_ALT)

    def _safe(txt: Any, limit: int = 420) -> str:
        s = str(txt or "—").strip()
        return s if len(s) <= limit else s[: limit - 3] + "..."

    # =========================================================================
    # PAGINA 1: COPERTINA ED EXECUTIVE SUMMARY
    # =========================================================================
    pdf.add_page()
    pdf.set_y(18)
    pdf.set_font(f_fam, "B", 8.8)
    pdf.set_text_color(*COLOR_TEAL)
    pdf.cell(pdf.epw, 4.8, f"RELAZIONE DI PRE-ANALISI CCII | {draft_date.upper()}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4.0)

    pdf.set_font(f_fam, "B", 22.0)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw, 9.5, "Crisi d'impresa", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.multi_cell(pdf.epw, 9.5, client_name, align="L")
    pdf.ln(2.5)

    pdf.set_font(f_fam, "", 10.5)
    pdf.set_text_color(*COLOR_SUBTITLE)
    cf_txt = f" · CF/P.IVA {header.get('codice_fiscale')}" if header.get("codice_fiscale") else ""
    pdf.cell(pdf.epw, 5.2, f"{forma_giuridica}{cf_txt}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(pdf.epw, 5.2, header.get("sottotitolo") or "Ricostruzione economico-finanziaria, debitoria e prima valutazione CCII", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(4.0)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.set_line_width(0.35)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(5.5)

    cards_y = pdf.get_y()
    card_w = (pdf.epw - 9) / 4
    card_h = 31.0
    cards_list = (header.get("executive_cards") or [])[:4]
    while len(cards_list) < 4:
        cards_list.append({"valore": "n.d.", "etichetta": "Dato non disponibile"})

    for i, c in enumerate(cards_list):
        cx = 15 + i * (card_w + 3)
        pdf.set_fill_color(*COLOR_CARD_BG)
        pdf.set_draw_color(*COLOR_BORDER)
        pdf.rect(cx, cards_y, card_w, card_h, style="DF")
        pdf.set_fill_color(*COLOR_TEAL)
        pdf.rect(cx, cards_y, card_w, 1.5, style="F")

        pdf.set_xy(cx + 2.5, cards_y + 5.8)
        pdf.set_font(f_fam, "B", 11.8)
        pdf.set_text_color(*COLOR_NAVY)
        pdf.cell(card_w - 5, 5.5, _safe(c.get("valore"), 24), align="L")

        pdf.set_xy(cx + 2.5, cards_y + 14.0)
        pdf.set_font(f_fam, "", 7.9)
        pdf.set_text_color(*COLOR_TEXT_MUTED)
        pdf.multi_cell(card_w - 5, 3.8, _safe(c.get("etichetta"), 60), align="L")

    pdf.set_y(cards_y + card_h + 4.5)
    pdf.section_title("Esito sintetico della pre-analisi", top_gap=1.0)
    for item in (fp.get("esito_preanalisi") or [])[:4]:
        if ":" in item:
            lead, rest = item.split(":", 1)
            pdf.bullet(f"{lead.strip()}:", rest.strip(), line_height=4.8, size_pt=9.2, gap_after=2.6)
        else:
            pdf.bullet("Sintesi:", item, line_height=4.8, size_pt=9.2, gap_after=2.6)

    pdf.ln(2.0)
    pdf.framed_box(
        "Scopo, metodo epistemologico e perimetro giuridico",
        f"{_safe(c1.get('scopo'), 380)}\n\n"
        + (
            "Profilo giuridico applicato: Società di capitali con autonomia patrimoniale perfetta (art. 2462 c.c.); verifica estesa a garanzie personali soci/amministratori, postergazione finanziamenti soci (art. 2467 c.c.), integrità capitale (art. 2482-ter c.c.) e adeguati assetti (art. 2086 c.c.)."
            if is_srl
            else "Profilo giuridico applicato: Impresa individuale / Persona fisica ex art. 2740 c.c. (responsabilità illimitata con confusione tra patrimonio aziendale e personale); verifica soglie dimensionali art. 2 CCII."
        ),
        title_size=9.2,
        body_size=8.4,
        line_height=4.5,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=4.4,
        pad_y=3.8,
    )

    # =========================================================================
    # PAGINA 2: 01 / PROFILO SOCIETARIO E CONTO ECONOMICO COMPARATO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("01", "Profilo e Conto Economico Comparato")

    pdf.section_title("Inquadramento anagrafico e attività", top_gap=0)
    pdf.body_p(
        f"Soggetto: {c2.get('denominazione', client_name)} ({c2.get('forma_giuridica', forma_giuridica)}). "
        f"CF/P.IVA: {c2.get('cf_piva', 'n.d.')} · REA: {c2.get('rea', 'n.d.')} · Sede: {c2.get('sede_legale', 'n.d.')} · "
        f"ATECO: {c2.get('codice_ateco', 'n.d.')} ({_safe(c2.get('attivita_prevalente'), 140)}).",
        line_height=4.6, size_pt=8.7, gap_after=3.0,
    )

    esercizi = (c3.get("esercizi") or [])[-4:]
    pdf.section_title("Conto economico comparato (Bilanci / Situazioni contabili)", top_gap=0.5)
    if esercizi:
        n_ex = len(esercizi)
        first_w = 56.0
        col_ex_w = (pdf.epw - first_w) / n_ex
        widths_ce = tuple([first_w] + [col_ex_w] * n_ex)
        aligns_ce = tuple(["LEFT"] + ["RIGHT"] * n_ex)
        with pdf.table(
            col_widths=widths_ce,
            headings_style=header_style,
            line_height=4.7,
            padding=(1.2, 1.4),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=aligns_ce,
        ) as table:
            row = table.row()
            row.cell("Voce Conto Economico (€)")
            for ex in esercizi:
                row.cell(str(ex.get("anno", "—")))

            metrics = [
                ("Ricavi delle vendite (A.1)", "ricavi_a1", False),
                ("Altri ricavi e proventi (A.2-A.5)", "altri_ricavi_a2_a5", False),
                ("Valore della Produzione (A)", "valore_produzione_a", True),
                ("Costi della Produzione (B) operativi", "costi_produzione_b", False),
                ("MOL / EBITDA [OIC 12]", "mol", True),
                ("Ammortamenti esposti", "ammortamenti", False),
                ("Risultato Netto d'esercizio", "utile_perdita", True),
            ]
            for r_idx, (lbl, key, is_b) in enumerate(metrics):
                st = highlight_style if is_b else (cell_white if r_idx % 2 == 0 else cell_alt)
                row = table.row(style=st)
                row.cell(lbl, style=bold_style if is_b else None)
                for ex in esercizi:
                    row.cell(_fmt_eur(ex.get(key)), style=bold_style if is_b else None)
    else:
        pdf.body_p("Nessun conto economico storico normalizzato presente nel fascicolo.", size_pt=8.7)

    pdf.ln(3.0)
    pdf.section_title("Lettura economica e dato infrannuale", top_gap=0.5)
    pdf.body_p(_safe(c3.get("commento_periodo"), 520), line_height=4.6, size_pt=8.7, gap_after=2.5)
    dato_corr = (c4.get("dato") or {})
    if dato_corr and dato_corr.get("ricavi_a1") is not None:
        pdf.framed_box(
            f"Aggiornamento infrannuale ({dato_corr.get('periodo', 'corrente')})",
            f"Ricavi: {_fmt_eur(dato_corr.get('ricavi_a1'))} · Valore Produzione: {_fmt_eur(dato_corr.get('valore_produzione_a'))} · "
            f"MOL: {_fmt_eur(dato_corr.get('mol'))} · Risultato: {_fmt_eur(dato_corr.get('utile_perdita'))}.\n{_safe(c4.get('prudenza'), 260)}",
            title_size=8.6, body_size=8.0, line_height=4.1, accent_color=COLOR_TEAL, bg_color=COLOR_CARD_BG,
        )

    # =========================================================================
    # PAGINA 3: 02 / INDEBITAMENTO RICOSTRUITO DA BILANCIO E SINTESI MASSA
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("02", "Indebitamento Ricostruito (Bilancio vs Banche Dati)")

    t51 = c5.get("tabella_5_1") or {}
    col51 = t51.get("colonne") or []
    rows51 = (t51.get("righe") or [])[:10]
    pdf.section_title("Evoluzione debiti da bilancio / situazioni contabili", top_gap=0)
    if col51 and rows51:
        n_c = len(col51)
        w0 = 64.0
        wc = (pdf.epw - w0) / n_c
        with pdf.table(
            col_widths=tuple([w0] + [wc] * n_c),
            headings_style=header_style,
            line_height=4.4,
            padding=(1.1, 1.3),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=tuple(["LEFT"] + ["RIGHT"] * n_c),
        ) as table:
            row = table.row()
            row.cell("Voce Stato Patrimoniale")
            for c in col51:
                row.cell(str(c.get("label", c.get("key", ""))))
            for r_idx, r in enumerate(rows51):
                row = table.row(style=cell_white if r_idx % 2 == 0 else cell_alt)
                row.cell(_safe(r.get("voce"), 42))
                for c in col51:
                    val = (r.get("valori") or {}).get(c.get("key"))
                    row.cell(_fmt_eur(val))
    else:
        pdf.body_p(_safe(c5.get("commento_5_1"), 450), line_height=4.5, size_pt=8.6)

    pdf.ln(2.5)
    t53 = c5.get("tabella_5_3_sintesi") or {}
    righe53 = (t53.get("righe") or [])[:9]
    pdf.section_title("Tabella 5.3 — Riconciliazione complessiva senza duplicazioni", top_gap=0.5)
    with pdf.table(
        col_widths=(56, 36, 26, 26, 36),
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.1),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "RIGHT", "RIGHT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Categoria debito")
        row.cell("Fonte primaria")
        row.cell("Stimato (€)")
        row.cell("Bilancio (€)")
        row.cell("Criterio / Note")
        for idx, r in enumerate(righe53):
            is_sub = "subtotale" in str(r.get("categoria", "")).lower()
            st = highlight_style if is_sub else (cell_white if idx % 2 == 0 else cell_alt)
            row = table.row(style=st)
            row.cell(_safe(r.get("categoria"), 48), style=bold_style if is_sub else None)
            row.cell(_safe(r.get("fonte"), 32))
            row.cell(_fmt_eur(r.get("importo_stimato")), style=bold_style if is_sub else None)
            row.cell(str(r.get("dato_bilancio_display") or _fmt_eur(r.get("dato_bilancio"))))
            row.cell(_safe(r.get("note"), 55))
        row = table.row(style=highlight_style)
        row.cell("TOTALE PASSIVO RICOSTRUITO", style=bold_style)
        row.cell("Sintesi integrata")
        row.cell(_fmt_eur(t53.get("totale_stimato")), style=bold_style)
        row.cell(_fmt_eur(t53.get("totale_bilancio")))
        row.cell("Esclude duplicazioni AdER/CR")

    # =========================================================================
    # PAGINA 4: 03 / BANCHE DATI ESTERNE, PFN E TEST PRATICO CNC
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("03", "Banche Dati Esterne, PFN e Test Pratico CNC")

    ader_raw = c5.get("tabella_5_2_ader")
    pdf.section_title("Esposizioni esattoriali (AdER) e rapporti creditizi (CR / CTC)", top_gap=0)
    if isinstance(ader_raw, dict) and float(ader_raw.get("totale_residuo") or 0.0) > 0:
        with pdf.table(
            col_widths=(88, 46, 46),
            headings_style=header_style,
            line_height=4.1,
            padding=(0.95, 1.0),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "RIGHT", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Voce Posizione AdER")
            row.cell("Importo (€)")
            row.cell("Nota tecnica")
            ader_items = [
                ("Carico originario affidato a ruolo", ader_raw.get("carico_affidato"), "Totale ruoli affidati"),
                ("Residuo capitale stimato", ader_raw.get("residuo_capitale"), "Quota capitale"),
                ("Interessi di mora e sanzioni", ader_raw.get("interessi_sanzioni"), "Eventuale falcidia in transazione"),
                ("Totale Residuo AdER netto da saldare", ader_raw.get("totale_residuo"), "Esposizione esattoriale netta"),
            ]
            for idx, (lbl_a, val_a, note_a) in enumerate(ader_items):
                is_tot_a = idx == len(ader_items) - 1
                row = table.row(style=highlight_style if is_tot_a else (cell_white if idx % 2 == 0 else cell_alt))
                row.cell(lbl_a, style=bold_style if is_tot_a else None)
                row.cell(_fmt_eur(val_a), style=bold_style if is_tot_a else None)
                row.cell(note_a)
    elif isinstance(ader_raw, list) and ader_raw:
        with pdf.table(
            col_widths=(26, 62, 34, 28, 30),
            headings_style=header_style,
            line_height=3.9,
            padding=(0.95, 1.0),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "LEFT", "LEFT", "RIGHT", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Ente / Natura")
            row.cell("Descrizione carico")
            row.cell("Codice / Atto")
            row.cell("Importo (€)")
            row.cell("Stato")
            for idx, r in enumerate(ader_raw[:10]):
                row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
                row.cell(_safe(r.get("ente") or r.get("natura") or "AdER", 22))
                row.cell(_safe(r.get("descrizione") or r.get("tributo"), 55))
                row.cell(_safe(r.get("numero_cartella") or r.get("documento"), 24))
                row.cell(_fmt_eur(r.get("residuo") if r.get("residuo") is not None else r.get("importo")))
                row.cell(_safe(r.get("stato"), 22))
    else:
        pdf.body_p("Nessuna cartella AdER caricata al fascicolo. Verificare comunque la posizione con estratto di ruolo aggiornato.", size_pt=8.7)

    cred_rows = (c5.get("tabella_5_2_credito") or [])[:8]
    if cred_rows:
        pdf.ln(2.0)
        with pdf.table(
            col_widths=(36, 48, 30, 30, 36),
            headings_style=header_style,
            line_height=3.9,
            padding=(0.95, 1.0),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "LEFT", "RIGHT", "RIGHT", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Fonte")
            row.cell("Intermediario / Forma")
            row.cell("Accordato (€)")
            row.cell("Utilizzato (€)")
            row.cell("Note")
            for idx, r in enumerate(cred_rows):
                row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
                row.cell(_safe(r.get("fonte"), 24))
                row.cell(_safe(r.get("intermediario"), 36))
                row.cell(_fmt_eur(r.get("accordato")))
                row.cell(_fmt_eur(r.get("utilizzato")))
                row.cell(_safe(r.get("note") or r.get("stato"), 28))

    pdf.ln(2.5)
    pfn = c5.get("tabella_pfn_esma") or {}
    pfn_eval = c5.get("valutazione_pfn_ebitda") or {}
    tp = c5.get("test_pratico_ministeriale") or {}
    pdf.framed_box(
        "Posizione Finanziaria Netta (ESMA 2021) e Test Pratico Ministeriale CNC",
        f"PFN Totale stimata: {_fmt_eur(pfn.get('pfn_totale'))} · Rapporto PFN/EBITDA: {pfn_eval.get('ratio', 'n.d.')} ({_safe(pfn_eval.get('valutazione_bancaria') or pfn_eval.get('giudizio'), 120)}).\n"
        f"Test Pratico CNC (D.D. 28/09/2021): Debito netto da risanare {_fmt_eur(tp.get('debito_netto_da_risanare') or tp.get('debito_da_risanare'))} · "
        f"Rapporto indicativo anni rimborso: {tp.get('rapporto', 'n.d.')} — {_safe(tp.get('giudizio') or tp.get('esito_sintetico'), 140)}.",
        title_size=8.8, body_size=8.1, line_height=4.2, accent_color=COLOR_NAVY, bg_color=COLOR_CARD_BG,
    )

    # =========================================================================
    # PAGINA 5: 04 / PATRIMONIO E REGIME RESPONSABILITÀ (SRL VS INDIVIDUALE)
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("04", "Patrimonio, Garanzie e Regime di Responsabilità")

    immobili = (c8.get("immobili") or [])[:10]
    pdf.section_title(f"Patrimonio immobiliare censito ({len(c8.get('immobili') or [])} unità)", top_gap=0)
    if immobili:
        with pdf.table(
            col_widths=(26, 48, 34, 16, 26, 30),
            headings_style=header_style,
            line_height=3.9,
            padding=(0.9, 1.0),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "LEFT", "LEFT", "CENTER", "RIGHT", "RIGHT"),
        ) as table:
            row = table.row()
            row.cell("Comune")
            row.cell("Indirizzo / Unità")
            row.cell("Dati Catastali")
            row.cell("Cat.")
            row.cell("Rendita (€)")
            row.cell("Val. Catast. (€)")
            for idx, im in enumerate(immobili):
                row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
                row.cell(_safe(im.get("comune"), 20))
                row.cell(_safe(im.get("indirizzo"), 38))
                row.cell(_safe(im.get("catasto"), 26))
                row.cell(_safe(im.get("categoria"), 10))
                row.cell(_fmt_eur(im.get("rendita")))
                row.cell(_fmt_eur(im.get("valore_catastale")))
    else:
        pdf.body_p(_safe(c8.get("esito_catastale") or "Nessun bene immobile censito al fascicolo.", 260), size_pt=8.7)

    pdf.ln(2.5)
    lotti = (c8.get("lotti_concorsuali") or [])[:5]
    if lotti:
        pdf.section_title("Stima indicativa di realizzo dell'attivo", top_gap=0.5)
        with pdf.table(
            col_widths=(66, 30, 30, 54),
            headings_style=header_style,
            line_height=4.0,
            padding=(0.95, 1.0),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "RIGHT", "RIGHT", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Classe / Lotto attivo")
            row.cell("Scenario Prudente")
            row.cell("Scenario Favorevole")
            row.cell("Criterio / Note")
            for idx, l in enumerate(lotti):
                row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
                row.cell(_safe(l.get("lotto"), 50))
                row.cell(str(l.get("prudente", "—")))
                row.cell(str(l.get("favorevole", "—")))
                row.cell(_safe(l.get("note"), 48))

    pdf.ln(2.5)
    esp_soci = (c8.get("esposizione_personale_soci") or [])[:4]
    pdf.section_title("Differenziazione giuridica: Società di Capitali vs Persona Fisica", top_gap=0.5)
    if is_srl:
        pdf.body_p(
            "In quanto S.r.l., vige la responsabilità limitata al patrimonio sociale (art. 2462 c.c.). L'analisi legale verifica: "
            "(1) eventuali fideiussioni personali dei soci/amministratori verso banche; (2) finanziamenti soci postergati ex art. 2467 c.c.; "
            "(3) perdite ex artt. 2482-bis / 2482-ter c.c.; (4) adeguati assetti organizzativi ex art. 2086 c.c. e art. 3 CCII.",
            line_height=4.5, size_pt=8.6, gap_after=2.5,
        )
    else:
        pdf.body_p(
            "In quanto impresa individuale / persona fisica, vige l'art. 2740 c.c.: assenza di separazione patrimoniale tra debiti aziendali e personali. "
            "L'analisi integra esposizioni fiscali, garanzie consumeristiche/coobbligazioni e verifica le soglie art. 2 CCII per concordato minore o liquidazione controllata.",
            line_height=4.5, size_pt=8.6, gap_after=2.5,
        )
    for es in esp_soci:
        pdf.bullet(f"{es.get('socio', 'Soggetto')}:", f"{es.get('garanzia', '')} ({es.get('importo', '—')})", line_height=4.3, size_pt=8.4, gap_after=1.5)

    # =========================================================================
    # PAGINA 6: 05 / DIAGNOSI DELLA CRISI, SOGLIE CCII E PUNTI DA VERIFICARE
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("05", "Diagnosi della Crisi, Soglie CCII e Criticità")

    diag = c7.get("diagnosi_semaforo") or {}
    inquadr = c7.get("inquadramento_ccii") or {}
    pdf.framed_box(
        f"Semaforo Diagnostico: {diag.get('etichetta', 'ISTRUTTORIA IN CORSO')}",
        f"{_safe(diag.get('descrizione') or diag.get('sintesi') or c7.get('principale_criticita'), 320)}\n"
        f"Inquadramento dimensionale (art. 2 lett. d) CCII): {_safe(inquadr.get('qualifica_giuridica') or inquadr.get('qualificazione') or 'Verifica soglie in corso', 180)}.",
        title_size=9.2, body_size=8.3, line_height=4.4, accent_color=COLOR_NAVY, bg_color=COLOR_CARD_BG,
    )
    pdf.ln(2.5)

    pdf.section_title("Elementi favorevoli e criticità prioritarie", top_gap=0.5)
    for ef in (c7.get("elementi_favorevoli") or [])[:3]:
        pdf.bullet("Elemento favorevole:", _safe(ef, 180), line_height=4.3, size_pt=8.5, gap_after=1.6)
    for cr_item in (c7.get("cinque_principali_criticita") or [])[:4]:
        if isinstance(cr_item, dict):
            pdf.bullet(f"[{cr_item.get('gravita') or cr_item.get('livello') or 'ATTENZIONE'}] {cr_item.get('titolo', 'Criticità')}:", _safe(cr_item.get("descrizione") or cr_item.get("dettaglio"), 170), line_height=4.3, size_pt=8.5, gap_after=1.6)
        else:
            pdf.bullet("Criticità:", _safe(cr_item, 180), line_height=4.3, size_pt=8.5, gap_after=1.6)

    pdf.ln(2.0)
    pdf.section_title("Incongruenze e punti da verificare nel fascicolo", top_gap=0.5)
    for p in c6[:5]:
        pdf.bullet(f"[{p.get('gravita', 'VERIFICA')}] {_safe(p.get('documenti'), 36)}:", _safe(p.get("descrizione"), 165), line_height=4.2, size_pt=8.3, gap_after=1.6)

    # =========================================================================
    # PAGINA 7: 06 / SCENARI CCII, DOCUMENTI MANCANTI E CONCLUSIONE
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("06", "Scenari di Risanamento, Documenti Mancanti e Conclusione")

    scenari = (c9.get("scenari") or [])[:4]
    pdf.section_title("Confronto strumenti di regolazione della crisi (CCII)", top_gap=0)
    if scenari:
        with pdf.table(
            col_widths=(44, 34, 102),
            headings_style=header_style,
            line_height=4.1,
            padding=(1.0, 1.1),
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.NONE,
            text_align=("LEFT", "CENTER", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Strumento CCII")
            row.cell("Fattibilità")
            row.cell("Motivazione e Presupposti Operativi")
            for idx, sc in enumerate(scenari):
                row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
                row.cell(_safe(sc.get("scenario") or sc.get("strumento") or sc.get("nome"), 42), style=bold_style)
                row.cell(_safe(sc.get("fattibilita") or "IN VERIFICA", 22), style=bold_style)
                row.cell(_safe(sc.get("motivazione") or sc.get("vantaggi") or sc.get("descrizione"), 155))

    pdf.ln(2.5)
    pdf.section_title("Documentazione indispensabile da acquisire", top_gap=0.5)
    docs_manc = (c10.get("documenti_indispensabili_prioritari") or c10.get("documenti_mancanti") or [])[:5]
    if docs_manc:
        for dm in docs_manc:
            txt_dm = dm.get("documento") if isinstance(dm, dict) else str(dm)
            pdf.bullet("Integrazione richiesta:", _safe(txt_dm, 175), line_height=4.2, size_pt=8.4, gap_after=1.5)
    else:
        pdf.bullet("Fascicolo documentale:", "Documentazione principale presente; acquisire aggiornamenti di cassa e partitari.", line_height=4.2, size_pt=8.4, gap_after=1.5)

    pdf.ln(2.0)
    pdf.section_title("Orientamento conclusivo (Human Gate)", top_gap=0.5)
    pdf.body_p(_safe(c11.get("giudizio_sintetico") or c9.get("motivazione"), 360), line_height=4.5, size_pt=8.7, gap_after=2.5)
    pdf.framed_box(
        "Regola di validazione finale e tracciabilità Audit",
        _safe(c11.get("regola_finale_human_gate"), 320),
        title_size=8.5, body_size=7.9, line_height=4.0, accent_color=COLOR_TEAL, bg_color=COLOR_CARD_BG,
    )

    return bytes(pdf.output())
