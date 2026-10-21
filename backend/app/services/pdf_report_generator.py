"""Generatore PDF nativo per il Report di Preanalisi ex CCII di DossierLex.

Realizzato con fpdf2 per una resa grafica vettoriale istituzionale:
- Supporto UTF-8 completo (caratteri accentati italiani, simbolo Euro €)
- Tavolozza istituzionale DossierLex (Verde Oliva #2d3628, Accento Cuoio #6c5c42, Superfici calde)
- Nessuna intestazione ripetuta su ogni pagina (riservatezza e intestazione solo in copertina su pagina 1)
- Numerazione dinamica 'Pagina X di {nb}' nel footer pulito
- Tabelle dinamiche con impaginazione automatica e ripetizione automatica intestazioni colonne
- Supporto dinamico orientamento Verticale (Portrait) e Orizzontale (Landscape)
"""

import os
from typing import Dict, Any, List, Optional
from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode, TableBordersLayout, XPos, YPos


# Palette cromatica DossierLex
COLOR_PRIMARY = (45, 54, 40)        # #2d3628 Verde oliva istituzionale
COLOR_ACCENT = (108, 92, 66)        # #6c5c42 Cuoio dorato
COLOR_TEXT_DARK = (34, 38, 34)      # #222622 Testo principale
COLOR_TEXT_MUTED = (105, 112, 102)  # #697066 Testo secondario
COLOR_BORDER = (215, 219, 213)      # #d7dbd5 Bordi tabelle e separatori
COLOR_BG_ALT = (248, 249, 247)      # #f8f9f7 Righe alternate
COLOR_BG_BOX = (245, 247, 244)      # #f5f7f4 Box di evidenziazione
COLOR_AMBER_BG = (254, 249, 235)    # #fef9eb Avviso / Prudenza
COLOR_AMBER_BORDER = (217, 119, 6)  # #d97706
COLOR_RED_BG = (254, 242, 242)      # #fef2f2 Criticità
COLOR_RED_BORDER = (220, 38, 38)    # #dc2626
COLOR_GREEN_BG = (240, 253, 244)    # #f0fdf4 Elementi favorevoli
COLOR_GREEN_BORDER = (22, 163, 74)  # #16a34a
COLOR_WHITE = (255, 255, 255)


def _fmt_eur(v) -> str:
    if v is None:
        return "—"
    try:
        n = float(v)
        return f"€ {n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(v)


class PreanalysisPDF(FPDF):
    """Sottoclasse FPDF personalizzata per il report DossierLex."""

    def __init__(self, orientation="portrait", draft_date=""):
        # A4: 210 x 297 mm
        super().__init__(orientation=orientation, unit="mm", format="A4")
        self.draft_date = draft_date
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(left=15, top=15, right=15)
        self.alias_nb_pages()
        self._setup_fonts()

    def _setup_fonts(self):
        """Configura i font DejaVu con supporto completo ai caratteri UTF-8."""
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
        """NON ripete l'intestazione su ogni pagina, come esplicitamente richiesto dall'utente.
        L'intestazione formale appare unicamente nella prima pagina del documento.
        """
        pass

    def footer(self):
        """Piè di pagina pulito: dicitura discreta a sinistra, data e numerazione dinamica a destra."""
        self.set_y(-14)
        self.set_font(self.font_family_name, "", 8)
        self.set_text_color(*COLOR_TEXT_MUTED)

        # Linea divisoria sottile
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(2)

        # Sinistra: DossierLex + Data
        left_text = "DossierLex — Crisi d'Impresa ex CCII"
        if self.draft_date:
            left_text += f" | Elaborato il {self.draft_date}"

        self.cell(self.epw / 2, 5, left_text, align="L")
        # Destra: Pagina X di {nb}
        self.cell(self.epw / 2, 5, f"Pagina {self.page_no()} di {{nb}}", align="R")

    # -------------------------------------------------------------------------
    # COMPONENTI GRAFICI DI STILE
    # -------------------------------------------------------------------------
    def render_cover_header(self, header_data: Dict[str, Any]):
        """Renderizza l'intestazione formale istituzionale di copertina su Pagina 1."""
        client_name = header_data.get("cliente") or "CLIENTE"
        legal_form = header_data.get("forma_giuridica") or ""
        cf_piva = header_data.get("codice_fiscale") or ""
        titolo = header_data.get("titolo") or "PREANALISI ECONOMICO-FINANZIARIA E IPOTESI DI RISANAMENTO"
        sottotitolo = header_data.get("sottotitolo") or "Composizione Negoziata della Crisi — Ipotesi preliminare ex CCII"
        riservatezza = header_data.get("riservatezza") or "DOCUMENTO DI LAVORO RISERVATO"
        data_bozza = header_data.get("data_bozza") or self.draft_date

        # Top Bar: Brand DossierLex + Badge Riservatezza
        self.set_font(self.font_family_name, "B", 10)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(self.epw * 0.65, 5, "DOSSIERLEX — CRISI D'IMPRESA E SOVRAINDEBITAMENTO", align="L")

        self.set_font(self.font_family_name, "B", 8)
        self.set_text_color(*COLOR_RED_BORDER)
        self.cell(self.epw * 0.35, 5, riservatezza.upper(), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_font(self.font_family_name, "", 9)
        self.set_text_color(*COLOR_TEXT_MUTED)
        self.cell(self.epw * 0.65, 5, "Studio Legale Avv. Aurelio Bentivegna & Partners", align="L")
        self.cell(self.epw * 0.35, 5, f"Data di elaborazione: {data_bozza}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Linea divisoria principale d'accento
        self.ln(2)
        self.set_draw_color(*COLOR_PRIMARY)
        self.set_line_width(0.8)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)

        # Titolo Documento
        self.set_font(self.font_family_name, "B", 15)
        self.set_text_color(*COLOR_PRIMARY)
        self.multi_cell(self.epw, 7, titolo, align="L")
        self.ln(1)

        # Sottotitolo
        self.set_font(self.font_family_name, "", 10)
        self.set_text_color(*COLOR_ACCENT)
        self.multi_cell(self.epw, 5, sottotitolo, align="L")
        self.ln(4)

        # Riquadro Riassuntivo Anagrafica Cliente
        box_y = self.get_y()
        self.set_fill_color(*COLOR_BG_BOX)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.3)
        self.rect(self.l_margin, box_y, self.epw, 18, style="DF")

        self.set_xy(self.l_margin + 4, box_y + 3)
        self.set_font(self.font_family_name, "B", 11)
        self.set_text_color(*COLOR_PRIMARY)
        self.cell(self.epw - 8, 5, f"{client_name.upper()} ({legal_form.upper()})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_xy(self.l_margin + 4, box_y + 9)
        self.set_font(self.font_family_name, "", 9)
        self.set_text_color(*COLOR_TEXT_DARK)
        cf_label = f"Codice Fiscale / P.IVA: {cf_piva}" if cf_piva else "Codice Fiscale: non comunicato"
        self.cell(self.epw - 8, 5, cf_label, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.set_y(box_y + 22)

    def chapter_banner(self, num_str: str, title: str):
        """Renderizza il banner a tutta larghezza con sfondo verde oliva istituzionale."""
        if self.get_y() > (self.h - 45):
            self.add_page()

        self.ln(4)
        y = self.get_y()
        banner_h = 8.5
        self.set_fill_color(*COLOR_PRIMARY)
        self.rect(self.l_margin, y, self.epw, banner_h, style="F")

        self.set_xy(self.l_margin + 4, y + 1.5)
        self.set_font(self.font_family_name, "B", 10.5)
        self.set_text_color(*COLOR_WHITE)
        self.cell(self.epw - 8, 5.5, f"CAPITOLO {num_str} — {title.upper()}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_y(y + banner_h + 3)

    def section_heading(self, title: str):
        """Titolo di sottosezione (10pt in grassetto color cuoio/accento)."""
        if self.get_y() > (self.h - 35):
            self.add_page()
        self.ln(2)
        self.set_font(self.font_family_name, "B", 10)
        self.set_text_color(*COLOR_ACCENT)
        self.cell(self.epw, 6, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1)

    def body_paragraph(self, text: str):
        """Paragrafo di testo ordinario con spaziatura coerente e interlinea leggibile."""
        if not text:
            return
        self.set_font(self.font_family_name, "", 9)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.multi_cell(self.epw, 4.8, str(text), align="J")
        self.ln(2)

    def callout_box(self, title: str, text: str, tone: str = "neutral"):
        """Riquadro di attenzione/cautela con bordo sinistro evidenziato."""
        if not text:
            return
        if self.get_y() > (self.h - 40):
            self.add_page()

        if tone == "warn":
            bg_col = COLOR_AMBER_BG
            border_col = COLOR_AMBER_BORDER
            title_col = (180, 83, 9)
        elif tone == "danger":
            bg_col = COLOR_RED_BG
            border_col = COLOR_RED_BORDER
            title_col = COLOR_RED_BORDER
        elif tone == "ok":
            bg_col = COLOR_GREEN_BG
            border_col = COLOR_GREEN_BORDER
            title_col = COLOR_GREEN_BORDER
        else:
            bg_col = COLOR_BG_BOX
            border_col = COLOR_ACCENT
            title_col = COLOR_PRIMARY

        y_start = self.get_y()
        self.set_font(self.font_family_name, "", 8.5)
        text_lines = self.multi_cell(self.epw - 10, 4.2, str(text), dry_run=True, output="LINES")
        est_height = 8 + (len(text_lines) * 4.2) + (5 if title else 0)

        if (y_start + est_height) > (self.h - 20):
            self.add_page()
            y_start = self.get_y()

        self.set_fill_color(*bg_col)
        self.set_draw_color(*COLOR_BORDER)
        self.set_line_width(0.2)
        self.rect(self.l_margin, y_start, self.epw, est_height, style="DF")

        # Bordo sinistro colorato
        self.set_fill_color(*border_col)
        self.rect(self.l_margin, y_start, 2.5, est_height, style="F")

        # Testo interno
        curr_y = y_start + 2.5
        if title:
            self.set_xy(self.l_margin + 5, curr_y)
            self.set_font(self.font_family_name, "B", 9)
            self.set_text_color(*title_col)
            self.cell(self.epw - 10, 4, title.upper(), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            curr_y += 4.5

        self.set_xy(self.l_margin + 5, curr_y)
        self.set_font(self.font_family_name, "", 8.5)
        self.set_text_color(*COLOR_TEXT_DARK)
        self.multi_cell(self.epw - 10, 4.2, str(text), align="J")
        self.set_y(y_start + est_height + 3)

    def bullet_list(self, items: List[str]):
        """Renderizza una lista puntata pulita."""
        if not items:
            return
        self.set_font(self.font_family_name, "", 9)
        self.set_text_color(*COLOR_TEXT_DARK)
        bullet_w = 4
        text_w = self.epw - bullet_w
        for it in items:
            if not it:
                continue
            if self.get_y() > (self.h - 25):
                self.add_page()
            y_pos = self.get_y()
            self.set_xy(self.l_margin, y_pos)
            self.set_font(self.font_family_name, "B", 9)
            self.set_text_color(*COLOR_ACCENT)
            self.cell(bullet_w, 4.8, "•")
            self.set_xy(self.l_margin + bullet_w, y_pos)
            self.set_font(self.font_family_name, "", 9)
            self.set_text_color(*COLOR_TEXT_DARK)
            self.multi_cell(text_w, 4.8, str(it))
            self.ln(1)
        self.ln(1)


# =============================================================================
# COSTRUTTORE REPORT COMPLETO
# =============================================================================
def generate_preanalysis_pdf(report_data: Dict[str, Any], orientation: str = "portrait") -> bytes:
    """Genera i byte del file PDF completo della preanalisi ex CCII."""
    header_data = report_data.get("header", {})
    draft_date = header_data.get("data_bozza", "")

    pdf = PreanalysisPDF(orientation=orientation, draft_date=draft_date)
    pdf.add_page()

    # 1. Copertina & Intestazione iniziale
    pdf.render_cover_header(header_data)

    # Stili per intestazione tabelle fpdf2
    header_style = FontFace(
        family=pdf.font_family_name,
        emphasis="B",
        size_pt=8.5,
        color=COLOR_WHITE,
        fill_color=COLOR_PRIMARY,
    )
    bold_style = FontFace(
        family=pdf.font_family_name,
        emphasis="B",
        size_pt=8.5,
        color=COLOR_TEXT_DARK,
    )
    accent_bold_style = FontFace(
        family=pdf.font_family_name,
        emphasis="B",
        size_pt=8.5,
        color=COLOR_PRIMARY,
        fill_color=COLOR_BG_BOX,
    )

    # -------------------------------------------------------------------------
    # CAPITOLO 1: PREMESSA E FINALITÀ
    # -------------------------------------------------------------------------
    c1 = report_data.get("capitolo_1_premessa", {})
    pdf.chapter_banner("1", "Premessa e Finalità della Preanalisi")
    pdf.body_paragraph(c1.get("scopo", ""))

    docs = c1.get("documenti_utilizzati", [])
    if docs:
        pdf.section_heading("Documenti Utilizzati ed Esaminati")
        col_w = (pdf.epw * 0.38, pdf.epw * 0.20, pdf.epw * 0.27, pdf.epw * 0.15)
        with pdf.table(
            col_widths=col_w,
            headings_style=header_style,
            line_height=5,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "LEFT", "CENTER"),
        ) as table:
            row = table.row()
            row.cell("Tipo Documento")
            row.cell("Anno / Periodo")
            row.cell("Descrizione / Titolo")
            row.cell("Stato")

            for d in docs:
                row = table.row()
                row.cell(str(d.get("tipo", "—")))
                row.cell(str(d.get("anno_periodo") or d.get("data") or "—"))
                row.cell(str(d.get("titolo") or d.get("fonte") or "—"))
                row.cell(str(d.get("stato", "Disponibile")))
        pdf.ln(3)

    if c1.get("flusso_annuo_destinabile"):
        pdf.callout_box(
            "Riserva Metodologica sul Flusso Finanziario",
            c1.get("flusso_annuo_destinabile", ""),
            tone="warn"
        )

    # -------------------------------------------------------------------------
    # CAPITOLO 2: PROFILO DELL'IMPRESA E NATURA DELLA CRISI
    # -------------------------------------------------------------------------
    c2 = report_data.get("capitolo_2_profilo", {})
    pdf.chapter_banner("2", "Profilo dell'Impresa e Natura della Crisi")

    # Tabella Anagrafica Società
    pdf.section_heading("2.1 Dati Identificativi dell'Impresa")
    anag_w = (pdf.epw * 0.28, pdf.epw * 0.72)
    with pdf.table(
        col_widths=anag_w,
        headings_style=header_style,
        line_height=4.8,
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.EVEN_ROWS,
        cell_fill_color=COLOR_BG_ALT,
        text_align=("LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Parametro Societario")
        row.cell("Dato Rilevato da Fonti Ufficiali")

        info_rows = [
            ("Denominazione Sociale", c2.get("denominazione", "—")),
            ("Forma Giuridica", c2.get("forma_giuridica", "—")),
            ("Codice Fiscale / P.IVA", c2.get("cf_piva", "—")),
            ("Numero R.E.A.", c2.get("rea", "—")),
            ("Sede Legale", c2.get("sede_legale", "—")),
            ("Data Costituzione", c2.get("data_costituzione", "—")),
            ("Capitale Sociale", _fmt_eur(c2.get("capitale_sociale"))),
            ("Codice ATECO", c2.get("codice_ateco", "—")),
            ("Attività Esercitata", c2.get("attivita_prevalente", "—")),
        ]
        for label, val in info_rows:
            row = table.row()
            row.cell(label, style=bold_style)
            row.cell(str(val))
    pdf.ln(3)

    # Tabella Soci
    soci = c2.get("soci", [])
    if soci:
        pdf.section_heading("2.2 Compagine Sociale e Governance")
        soci_w = (pdf.epw * 0.35, pdf.epw * 0.25, pdf.epw * 0.15, pdf.epw * 0.25)
        with pdf.table(
            col_widths=soci_w,
            headings_style=header_style,
            line_height=4.8,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "CENTER", "LEFT"),
        ) as table:
            row = table.row()
            row.cell("Nominativo Socio")
            row.cell("Codice Fiscale")
            row.cell("Quota %")
            row.cell("Carica / Ruolo")

            for s in soci:
                row = table.row()
                s_name = s.get("nome") or s.get("nominativo") or "—"
                row.cell(str(s_name), style=bold_style)
                row.cell(str(s.get("cf", "—")))
                quota = s.get("quota_pct", 0)
                row.cell(f"{quota}%" if quota else "—")
                row.cell(str(s.get("ruolo", "Socio")))
        pdf.ln(3)

    if c2.get("natura_crisi"):
        pdf.callout_box("Diagnosi sulla Natura della Crisi", c2.get("natura_crisi", ""), tone="neutral")

    # -------------------------------------------------------------------------
    # CAPITOLO 3: ANALISI ECONOMICA TRIENNALE
    # -------------------------------------------------------------------------
    c3 = report_data.get("capitolo_3_analisi_economica", {})
    pdf.chapter_banner("3", "Analisi Economica Triennale (Conto Economico)")
    pdf.body_paragraph(
        "Di seguito viene esposto il raffronto della gestione caratteristica ed economica ricavato dai bilanci "
        "d'esercizio approvati e depositati presso il Registro delle Imprese."
    )

    esercizi = c3.get("esercizi", [])
    if esercizi:
        num_es = len(esercizi)
        col_w_label = pdf.epw * 0.40
        col_w_num = (pdf.epw * 0.60) / num_es
        table_widths = [col_w_label] + [col_w_num] * num_es

        with pdf.table(
            col_widths=table_widths,
            headings_style=header_style,
            line_height=4.8,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=["LEFT"] + ["RIGHT"] * num_es,
        ) as table:
            head_row = table.row()
            head_row.cell("Voce di Conto Economico")
            for es in esercizi:
                head_row.cell(f"Esercizio {es.get('anno', '')}")

            metriche = [
                ("Ricavi delle vendite e prestazioni (A1)", "ricavi_a1", False, False),
                ("Altri ricavi e proventi (A2 - A5)", "altri_ricavi_a2_a5", False, False),
                ("Valore della Produzione (A)", "valore_produzione_a", True, True),
                ("Costi della Produzione (B)", "costi_produzione_b", False, False),
                ("Ammortamenti e svalutazioni", "ammortamenti", False, False),
                ("MOL / EBITDA Gestionale", "mol", True, True),
                ("Margine MOL % sul Valore Produzione", "mol_pct", False, False),
                ("Risultato d'Esercizio (Utile / Perdita)", "utile_perdita", True, True),
            ]

            for lbl, key, is_bold, is_highlight in metriche:
                row = table.row()
                row.cell(lbl, style=accent_bold_style if is_highlight else (bold_style if is_bold else None))
                for es in esercizi:
                    val = es.get(key)
                    if key == "mol_pct":
                        str_val = f"{val:.1f} %" if val is not None else "—"
                    else:
                        str_val = _fmt_eur(val)
                    row.cell(str_val, style=bold_style if is_bold else None)
        pdf.ln(3)

    if c3.get("commento_periodo"):
        pdf.body_paragraph(c3.get("commento_periodo", ""))

    anomalie = c3.get("anomalie_contabili", [])
    if anomalie:
        pdf.section_heading("Anomalie Contabili Rilevate dall'Esame dei Bilanci")
        pdf.bullet_list(anomalie)

    if c3.get("riscontro_dichiarazioni_redditi"):
        pdf.callout_box("Riscontro con Modelli Fiscali", c3.get("riscontro_dichiarazioni_redditi", ""), tone="ok")

    # -------------------------------------------------------------------------
    # CAPITOLO 4: IL DATO DELL'ANNO CORRENTE E NECESSITÀ DI PRUDENZA
    # -------------------------------------------------------------------------
    c4 = report_data.get("capitolo_4_dato_corrente", {})
    pdf.chapter_banner("4", "Il Dato dell'Anno Corrente e Necessità di Prudenza")

    d_infr = c4.get("dato")
    if d_infr:
        pdf.section_heading(f"Situazione Economica Infrannuale al {d_infr.get('periodo', 'Data Corrente')}")
        col_w = (pdf.epw * 0.50, pdf.epw * 0.50)
        with pdf.table(
            col_widths=col_w,
            headings_style=header_style,
            line_height=4.8,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "RIGHT"),
        ) as table:
            row = table.row()
            row.cell("Voce Gestionale Infrannuale")
            row.cell("Importo Rilevato")

            infr_items = [
                ("Ricavi caratteristici (A1)", _fmt_eur(d_infr.get("ricavi_a1"))),
                ("Valore della produzione (A)", _fmt_eur(d_infr.get("valore_produzione_a"))),
                ("Costi di produzione (B)", _fmt_eur(d_infr.get("costi_produzione_b"))),
                ("Ammortamenti e svalutazioni", _fmt_eur(d_infr.get("ammortamenti"))),
                ("Oneri finanziari di periodo", _fmt_eur(d_infr.get("oneri_finanziari"))),
                ("MOL / EBITDA di periodo", _fmt_eur(d_infr.get("mol"))),
                ("Risultato netto di periodo", _fmt_eur(d_infr.get("utile_perdita"))),
            ]
            for l, v in infr_items:
                r = table.row()
                r.cell(l, style=bold_style if "MOL" in l or "Risultato" in l else None)
                r.cell(v, style=bold_style if "MOL" in l or "Risultato" in l else None)
        pdf.ln(3)

    if c4.get("prudenza"):
        pdf.callout_box("Avvertenza di Prudenza Metodologica", c4.get("prudenza", ""), tone="warn")

    # -------------------------------------------------------------------------
    # CAPITOLO 5: ANALISI DELL'INDEBITAMENTO
    # -------------------------------------------------------------------------
    c5 = report_data.get("capitolo_5_indebitamento", {})
    pdf.chapter_banner("5", "Analisi dell'Indebitamento")

    # 5.1 Debiti da bilancio
    t5_1 = c5.get("tabella_5_1", {})
    t5_1_cols = t5_1.get("colonne", [])
    t5_1_rows = t5_1.get("righe", [])
    t5_1_tot = t5_1.get("totale_debiti", {})

    if t5_1_cols and t5_1_rows:
        pdf.section_heading("5.1 Struttura e Dinamica dei Debiti da Bilancio")
        num_cols = len(t5_1_cols)
        w_cat = pdf.epw * 0.36
        w_var = pdf.epw * 0.16
        w_data = (pdf.epw - w_cat - w_var) / num_cols
        col_widths = [w_cat] + [w_data] * num_cols + [w_var]

        with pdf.table(
            col_widths=col_widths,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=["LEFT"] + ["RIGHT"] * (num_cols + 1),
        ) as table:
            head = table.row()
            head.cell("Categoria di Debito")
            for c in t5_1_cols:
                head.cell(c.get("title", c.get("key", "")))
            head.cell("Variazione")

            for r in t5_1_rows:
                row = table.row()
                row.cell(str(r.get("categoria", "")), style=bold_style)
                vals = r.get("valori", {})
                for c in t5_1_cols:
                    k = c.get("key")
                    row.cell(_fmt_eur(vals.get(k)))
                var_val = r.get("variazione")
                row.cell(_fmt_eur(var_val) if var_val is not None else "—")

            if t5_1_tot:
                tot_row = table.row()
                tot_row.cell("TOTALE GENERALE DEBITI", style=accent_bold_style)
                tot_vals = t5_1_tot.get("valori", {})
                for c in t5_1_cols:
                    k = c.get("key")
                    tot_row.cell(_fmt_eur(tot_vals.get(k)), style=bold_style)
                tot_var = t5_1_tot.get("variazione")
                tot_row.cell(_fmt_eur(tot_var) if tot_var is not None else "—", style=bold_style)
        pdf.ln(3)

    if c5.get("commento_5_1"):
        pdf.body_paragraph(c5.get("commento_5_1", ""))

    # 5.2 Banche Dati Esterne (AdER e Credito)
    ader_data = c5.get("tabella_5_2_ader")
    if isinstance(ader_data, dict):
        pdf.section_heading("5.2 Posizione Fiscale da Estratto di Ruolo AdER")
        ader_w = (pdf.epw * 0.65, pdf.epw * 0.35)
        with pdf.table(
            col_widths=ader_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "RIGHT"),
        ) as table:
            head = table.row()
            head.cell("Voce Estratto di Ruolo AdER")
            head.cell("Importo Rilevato")

            ader_items = [
                ("Carico originariamente affidato", _fmt_eur(ader_data.get("carico_affidato"))),
                ("Sgravi riconosciuti", _fmt_eur(ader_data.get("sgravi"))),
                ("Pagamenti effettuati (rate rottamazione)", _fmt_eur(ader_data.get("pagamenti_effettuati"))),
                ("Stralcio / definizione agevolata", _fmt_eur(ader_data.get("stralcio_definizione"))),
                ("Residuo quota capitale", _fmt_eur(ader_data.get("residuo_capitale"))),
                ("Interessi e somme aggiuntive", _fmt_eur(ader_data.get("interessi_sanzioni"))),
            ]
            for lbl, val in ader_items:
                r = table.row()
                r.cell(lbl)
                r.cell(val)

            tot_r = table.row()
            tot_r.cell("TOTALE RESIDUO ADER", style=accent_bold_style)
            tot_r.cell(_fmt_eur(ader_data.get("totale_residuo")), style=accent_bold_style)
        pdf.ln(3)

        rott = ader_data.get("dettaglio_rottamazioni", [])
        if rott:
            pdf.section_heading("Dettaglio Definizioni Agevolate (Rottamazioni AdER)")
            rott_w = (pdf.epw * 0.35, pdf.epw * 0.20, pdf.epw * 0.25, pdf.epw * 0.20)
            with pdf.table(
                col_widths=rott_w,
                headings_style=header_style,
                line_height=4.6,
                borders_layout=TableBordersLayout.ALL,
                cell_fill_mode=TableCellFillMode.EVEN_ROWS,
                cell_fill_color=COLOR_BG_ALT,
                text_align=("LEFT", "RIGHT", "LEFT", "RIGHT"),
            ) as table:
                head = table.row()
                head.cell("Procedura / Norma")
                head.cell("Debito Originario")
                head.cell("Stato Rateazione")
                head.cell("Residuo Attuale")

                for rt in rott:
                    row = table.row()
                    row.cell(str(rt.get("procedura", "—")), style=bold_style)
                    row.cell(_fmt_eur(rt.get("debito_originario")))
                    row.cell(str(rt.get("stato", "—")))
                    row.cell(_fmt_eur(rt.get("residuo")), style=bold_style)
            pdf.ln(3)

    cred_rows = c5.get("tabella_5_2_credito", [])
    if isinstance(cred_rows, list) and cred_rows:
        pdf.section_heading("5.2 Posizioni Bancarie da Centrale Rischi, CTC e CRIF")
        cred_w = (pdf.epw * 0.28, pdf.epw * 0.24, pdf.epw * 0.16, pdf.epw * 0.16, pdf.epw * 0.16)
        with pdf.table(
            col_widths=cred_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "LEFT", "RIGHT", "RIGHT"),
        ) as table:
            head = table.row()
            head.cell("Fonte e Rilevazione")
            head.cell("Intermediario")
            head.cell("Rapporto")
            head.cell("Accordato")
            head.cell("Utilizzato / Residuo")

            for cr in cred_rows:
                row = table.row()
                row.cell(str(cr.get("fonte", "Centrale Rischi")))
                row.cell(str(cr.get("intermediario", "—")), style=bold_style)
                row.cell(str(cr.get("rapporto", "—")))
                row.cell(_fmt_eur(cr.get("accordato")))
                row.cell(_fmt_eur(cr.get("utilizzato")), style=bold_style)
        pdf.ln(3)

    # 5.3 Stima di Sintesi Massa Debitoria (Senza Duplicazioni)
    t5_3 = c5.get("tabella_5_3_sintesi", {})
    t5_3_rows = t5_3.get("righe", [])
    if t5_3_rows:
        pdf.section_heading("5.3 Stima di Sintesi della Massa Debitoria (Riconciliata senza Duplicazioni)")
        sint_w = (pdf.epw * 0.26, pdf.epw * 0.22, pdf.epw * 0.16, pdf.epw * 0.16, pdf.epw * 0.20)
        with pdf.table(
            col_widths=sint_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "RIGHT", "RIGHT", "LEFT"),
        ) as table:
            head = table.row()
            head.cell("Categoria Debitoria")
            head.cell("Fonte Rilevazione")
            head.cell("Importo Stimato")
            head.cell("Dato Bilancio")
            head.cell("Criterio / Note Riconciliazione")

            for sr in t5_3_rows:
                row = table.row()
                row.cell(str(sr.get("categoria", "—")), style=bold_style)
                row.cell(str(sr.get("fonte", "—")))
                row.cell(_fmt_eur(sr.get("importo_stimato")), style=bold_style)
                row.cell(_fmt_eur(sr.get("dato_bilancio")))
                row.cell(str(sr.get("note", "—")))

            tot_row = table.row()
            tot_row.cell("MASSA DEBITORIA COMPLESSIVA", style=accent_bold_style)
            tot_row.cell("Totale Riconciliato", style=accent_bold_style)
            tot_row.cell(_fmt_eur(t5_3.get("totale_stimato")), style=accent_bold_style)
            tot_row.cell(_fmt_eur(t5_3.get("totale_bilancio")), style=accent_bold_style)
            tot_row.cell("Escluse duplicazioni fiscali e bancarie", style=accent_bold_style)
        pdf.ln(3)

    if c5.get("cautele_sintesi"):
        pdf.callout_box("Cautele sulla Massa Debitoria", c5.get("cautele_sintesi", ""), tone="neutral")

    # -------------------------------------------------------------------------
    # CAPITOLO 6: PUNTI DA VERIFICARE
    # -------------------------------------------------------------------------
    c6 = report_data.get("capitolo_6_punti_verificare", [])
    pdf.chapter_banner("6", "Punti da Verificare e Discrepanze Rilevate")
    pdf.body_paragraph(
        "L'analisi trasversale dei documenti ha evidenziato le seguenti aree di anomalia o discordanza "
        "che necessitano di approfondimento e chiarimento prima della formalizzazione del piano."
    )

    if c6:
        punti_w = (pdf.epw * 0.35, pdf.epw * 0.15, pdf.epw * 0.22, pdf.epw * 0.28)
        with pdf.table(
            col_widths=punti_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "CENTER", "LEFT", "LEFT"),
        ) as table:
            head = table.row()
            head.cell("Anomalia o Aspetto Critico")
            head.cell("Gravità")
            head.cell("Documenti Coinvolti")
            head.cell("Azione Consigliata dallo Studio")

            for pv in c6:
                row = table.row()
                row.cell(str(pv.get("descrizione", "—")), style=bold_style)
                grav = str(pv.get("gravita", "VERIFICA")).upper()
                row.cell(grav, style=bold_style)
                row.cell(str(pv.get("documenti", "—")))
                row.cell(str(pv.get("azione", "—")))
        pdf.ln(3)

    # -------------------------------------------------------------------------
    # CAPITOLO 7: DIAGNOSI PRELIMINARE DELLA CRISI
    # -------------------------------------------------------------------------
    c7 = report_data.get("capitolo_7_diagnosi_crisi", {})
    pdf.chapter_banner("7", "Diagnosi Preliminare della Crisi")

    favs = c7.get("elementi_favorevoli", [])
    if favs:
        pdf.section_heading("7.1 Fattori di Solidità ed Elementi Favorevoli")
        pdf.bullet_list(favs)

    if c7.get("principale_criticita"):
        pdf.callout_box("7.2 Principale Criticità", c7.get("principale_criticita", ""), tone="danger")

    if c7.get("sintesi_vitalita"):
        pdf.callout_box("7.3 Giudizio di Vitalità Aziendale", c7.get("sintesi_vitalita", ""), tone="ok")

    # -------------------------------------------------------------------------
    # CAPITOLO 8: PATRIMONIO
    # -------------------------------------------------------------------------
    c8 = report_data.get("capitolo_8_patrimonio", {})
    pdf.chapter_banner("8", "Patrimonio e Garanzie")

    immobili = c8.get("immobili", [])
    if immobili:
        pdf.section_heading("8.1 Beni Immobili Intestati alla Società")
        imm_w = (pdf.epw * 0.08, pdf.epw * 0.24, pdf.epw * 0.22, pdf.epw * 0.12, pdf.epw * 0.17, pdf.epw * 0.17)
        with pdf.table(
            col_widths=imm_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("CENTER", "LEFT", "LEFT", "CENTER", "RIGHT", "RIGHT"),
        ) as table:
            head = table.row()
            head.cell("N.")
            head.cell("Indirizzo e Comune")
            head.cell("Dati Catastali")
            head.cell("Cat.")
            head.cell("Rendita")
            head.cell("Valore Catastale")

            for im in immobili:
                row = table.row()
                row.cell(str(im.get("numero", "")))
                addr = f"{im.get('indirizzo', '')}\n{im.get('comune', '')}"
                row.cell(addr)
                row.cell(str(im.get("catasto", "")))
                row.cell(str(im.get("categoria", "")))
                row.cell(_fmt_eur(im.get("rendita")))
                row.cell(_fmt_eur(im.get("valore_catastale")), style=bold_style)

            tot_cat = c8.get("totale_valore_catastale", 0.0)
            tot_row = table.row()
            tot_row.cell("", style=accent_bold_style)
            tot_row.cell("TOTALE COMPLESSIVO CATASTALE", style=accent_bold_style)
            tot_row.cell("", style=accent_bold_style)
            tot_row.cell("", style=accent_bold_style)
            tot_row.cell("", style=accent_bold_style)
            tot_row.cell(_fmt_eur(tot_cat), style=accent_bold_style)
        pdf.ln(3)

    veicoli = c8.get("veicoli", [])
    if veicoli:
        pdf.section_heading("8.2 Veicoli e Mezzi Aziendali")
        veic_w = (pdf.epw * 0.40, pdf.epw * 0.20, pdf.epw * 0.20, pdf.epw * 0.20)
        with pdf.table(
            col_widths=veic_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "CENTER", "CENTER", "RIGHT"),
        ) as table:
            head = table.row()
            head.cell("Marca e Modello")
            head.cell("Targa")
            head.cell("Anno")
            head.cell("Valore Stimato")

            for v in veicoli:
                row = table.row()
                row.cell(str(v.get("tipo", "—")), style=bold_style)
                row.cell(str(v.get("targa", "—")))
                row.cell(str(v.get("anno", "—")))
                row.cell(_fmt_eur(v.get("valore")))
        pdf.ln(3)

    cesp = c8.get("immobilizzazioni_materiali", {})
    if cesp.get("valore_netto_bilancio"):
        pdf.section_heading("8.3 Altre Immobilizzazioni Materiali da Bilancio")
        pdf.body_paragraph(
            f"Il valore contabile netto delle immobilizzazioni materiali ammonta a {_fmt_eur(cesp.get('valore_netto_bilancio'))}. "
            f"{cesp.get('note', '')}"
        )

    garanzie = c8.get("esposizione_personale_soci", [])
    if garanzie:
        pdf.section_heading("8.4 Garanzie Personali Prestate dai Soci (Fideiussioni)")
        gar_w = (pdf.epw * 0.30, pdf.epw * 0.50, pdf.epw * 0.20)
        with pdf.table(
            col_widths=gar_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "RIGHT"),
        ) as table:
            head = table.row()
            head.cell("Soggetto Fideiussore")
            head.cell("Oggetto della Garanzia / Beneficiario")
            head.cell("Importo Garantito")

            for g in garanzie:
                row = table.row()
                row.cell(str(g.get("socio", "—")), style=bold_style)
                row.cell(str(g.get("garanzia", "—")))
                row.cell(str(g.get("importo", "—")), style=bold_style)
        pdf.ln(3)

    # -------------------------------------------------------------------------
    # CAPITOLO 9: ORIENTAMENTO VERSO UNA SOLUZIONE EX CCII
    # -------------------------------------------------------------------------
    c9 = report_data.get("capitolo_9_orientamento_risanamento", {})
    pdf.chapter_banner("9", "Orientamento verso una Soluzione di Risanamento ex CCII")

    scenari = c9.get("scenari", [])
    if scenari:
        pdf.section_heading("9.1 Analisi Comparata degli Scenari Giuridici")
        scen_w = (pdf.epw * 0.30, pdf.epw * 0.16, pdf.epw * 0.54)
        with pdf.table(
            col_widths=scen_w,
            headings_style=header_style,
            line_height=4.8,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "CENTER", "LEFT"),
        ) as table:
            head = table.row()
            head.cell("Strumento Giuridico CCII")
            head.cell("Fattibilità")
            head.cell("Motivazione e Presupposti")

            for sc in scenari:
                row = table.row()
                row.cell(str(sc.get("scenario", "—")), style=bold_style)
                fatt = str(sc.get("fattibilita", "MEDIA")).upper()
                row.cell(fatt, style=bold_style)
                motiv = f"{sc.get('motivazione', '')}\n[Dati chiave: {sc.get('dati_chiave', '')}]"
                row.cell(motiv)
        pdf.ln(3)

    if c9.get("proposta_coerente"):
        pdf.callout_box(
            "9.2 Strumento Consigliato dallo Studio",
            f"STRUMENTO: {c9.get('proposta_coerente', '')}\n\n{c9.get('motivazione', '')}",
            tone="ok"
        )

    condizioni = c9.get("condizioni", [])
    if condizioni:
        pdf.section_heading("9.3 Condizioni Pregresse Necessarie")
        pdf.bullet_list(condizioni)

    # -------------------------------------------------------------------------
    # CAPITOLO 10: DOCUMENTAZIONE ANCORA NECESSARIA
    # -------------------------------------------------------------------------
    c10 = report_data.get("capitolo_10_documentazione", {})
    pdf.chapter_banner("10", "Documentazione Ancora Necessaria")

    doc_mancanti = c10.get("documenti_mancanti", [])
    if doc_mancanti:
        pdf.section_heading("Documenti e Chiarimenti da Fornire prima dell'Accesso alla Procedura")
        dm_w = (pdf.epw * 0.40, pdf.epw * 0.45, pdf.epw * 0.15)
        with pdf.table(
            col_widths=dm_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "CENTER"),
        ) as table:
            head = table.row()
            head.cell("Dato o Documento Mancante")
            head.cell("Finalità Giuridico-Economica")
            head.cell("Priorità")

            for dm in doc_mancanti:
                row = table.row()
                row.cell(str(dm.get("dato_mancante", "—")), style=bold_style)
                row.cell(str(dm.get("perche_serve", "—")))
                prio = str(dm.get("priorita", "ALTA")).upper()
                row.cell(prio, style=bold_style)
        pdf.ln(3)

    if c10.get("flusso_richiesto"):
        pdf.callout_box(
            "Requisito Fondamentale: Quantificazione del Flusso Annuo",
            c10.get("flusso_richiesto", ""),
            tone="warn"
        )

    # -------------------------------------------------------------------------
    # CAPITOLO 11: CONCLUSIONE PROVVISORIA
    # -------------------------------------------------------------------------
    c11 = report_data.get("capitolo_11_conclusione", {})
    pdf.chapter_banner("11", "Conclusione Provvisoria e Indicazioni per lo Studio")

    if c11.get("giudizio_sintetico"):
        pdf.body_paragraph(c11.get("giudizio_sintetico", ""))

    recs = c11.get("raccomandazioni", [])
    if recs:
        pdf.section_heading("Raccomandazioni Operative per il Professionista")
        pdf.bullet_list(recs)

    # Dicitura finale
    dicitura = c11.get("dicitura_finale") or f"PRIMA BOZZA DI ANALISI - ELABORATA IL {draft_date}"
    pdf.ln(4)
    pdf.set_font(pdf.font_family_name, "B", 9)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.cell(pdf.epw, 6, dicitura.upper(), align="CENTER", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # -------------------------------------------------------------------------
    # APPENDICE REGOLE DELLO STUDIO / PLAYBOOK
    # -------------------------------------------------------------------------
    rules = report_data.get("studio_rules", [])
    if rules:
        pdf.ln(6)
        if pdf.get_y() > (pdf.h - 50):
            pdf.add_page()
        pdf.chapter_banner("A", "Criteri Personalizzati dello Studio (Playbook DossierLex)")
        pdf.body_paragraph(
            "Il presente report integra i seguenti principi e criteri professionali acquisiti e convalidati "
            "dallo Studio Legale per garantire la massima accuratezza redazionale:"
        )

        rules_w = (pdf.epw * 0.28, pdf.epw * 0.22, pdf.epw * 0.50)
        with pdf.table(
            col_widths=rules_w,
            headings_style=header_style,
            line_height=4.6,
            borders_layout=TableBordersLayout.ALL,
            cell_fill_mode=TableCellFillMode.EVEN_ROWS,
            cell_fill_color=COLOR_BG_ALT,
            text_align=("LEFT", "LEFT", "LEFT"),
        ) as table:
            head = table.row()
            head.cell("Titolo Regola")
            head.cell("Sezione di Riferimento")
            head.cell("Istruzione Redazionale")

            for r in rules:
                row = table.row()
                row.cell(str(r.get("rule_title", "—")), style=bold_style)
                row.cell(str(r.get("scope_title", "Globale")))
                row.cell(str(r.get("rule_prompt", "—")))
        pdf.ln(3)

    return bytes(pdf.output())
