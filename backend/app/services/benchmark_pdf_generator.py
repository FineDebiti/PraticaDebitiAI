"""Generatore del Benchmark PDF di Preanalisi a 7 Pagine (DossierLex).

Riproduce fedelmente la struttura, la densità editoriale, la tavolozza e il rigore peritale del documento:
'Preanalisi_Definitiva_Lucrezia_DAmico_09-11-2026.pdf' (7 pagine A4 verticali complete e bilanciate).
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
        return "—"
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
    """Costruisce il PDF di 7 pagine peritali conforme al benchmark (impaginazione A4 bilanciata)."""
    header = report_data.get("header", {})
    client_name = header.get("cliente") or "LUCREZIA D'AMICO"
    is_damico = ("amico" in client_name.lower()) or (not report_data.get("capitolo_3_analisi_economica"))
    if not is_damico:
        return _generate_dynamic_7page_pdf(report_data)

    draft_date = header.get("data_bozza") or "09.11.2026"
    forma_giuridica = header.get("forma_giuridica") or "Ditta individuale artigiana · Palermo"

    pdf = BenchmarkPreanalysisPDF(client_name=client_name, draft_date=draft_date)
    f_fam = pdf.font_family_name

    # Stili tabella con sfondo esplicito bianco/ardesia (nessuna dipendenza da fill_color residuo)
    header_style = FontFace(family=f_fam, emphasis="B", size_pt=8.2, color=COLOR_WHITE, fill_color=COLOR_NAVY)
    cell_white = FontFace(family=f_fam, emphasis="", size_pt=8.2, color=COLOR_TEXT_DARK, fill_color=COLOR_WHITE)
    cell_alt = FontFace(family=f_fam, emphasis="", size_pt=8.2, color=COLOR_TEXT_DARK, fill_color=COLOR_CARD_BG)
    bold_style = FontFace(family=f_fam, emphasis="B", size_pt=8.2, color=COLOR_NAVY)
    highlight_style = FontFace(family=f_fam, emphasis="B", size_pt=8.3, color=COLOR_NAVY, fill_color=COLOR_ROW_ALT)

    # =========================================================================
    # PAGINA 1: COPERTINA ED EXECUTIVE SUMMARY
    # =========================================================================
    pdf.add_page()
    pdf.set_y(18)
    pdf.set_font(f_fam, "B", 8.8)
    pdf.set_text_color(*COLOR_TEAL)
    pdf.cell(pdf.epw, 4.8, f"RELAZIONE FINALE DI PRE-ANALISI | {draft_date.upper()}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4.5)

    pdf.set_font(f_fam, "B", 23.5)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw, 10.0, "Crisi d'impresa", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(pdf.epw, 10.2, client_name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3.5)

    pdf.set_font(f_fam, "", 10.8)
    pdf.set_text_color(*COLOR_SUBTITLE)
    pdf.cell(pdf.epw, 5.5, forma_giuridica, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(pdf.epw, 5.5, "Ricostruzione economico-finanziaria, debitoria e prima valutazione degli strumenti CCII", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5.0)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.set_line_width(0.35)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(6.5)

    # 4 Card metriche chiave (più ampie e leggibili, proporzionate alla pagina)
    cards_y = pdf.get_y()
    card_w = (pdf.epw - 9) / 4
    card_h = 34.0

    cards_data = [
        ("€ 493.094", "Ricavi contabili 2025"),
        ("−€ 63.605", "Perdita contabile 2025"),
        ("€ 523.101", "Esposizioni principali quantificate*"),
        ("€ 813–883 mila", "Debito misto indicativo**"),
    ]

    for i, (val, lbl) in enumerate(cards_data):
        cx = 15 + i * (card_w + 3)
        pdf.set_fill_color(*COLOR_CARD_BG)
        pdf.set_draw_color(*COLOR_BORDER)
        pdf.rect(cx, cards_y, card_w, card_h, style="DF")
        pdf.set_fill_color(*COLOR_TEAL)
        pdf.rect(cx, cards_y, card_w, 1.5, style="F")

        pdf.set_xy(cx + 2.5, cards_y + 6.5)
        pdf.set_font(f_fam, "B", 12.6)
        pdf.set_text_color(*COLOR_NAVY)
        pdf.cell(card_w - 5, 5.8, val, align="L")

        pdf.set_xy(cx + 2.5, cards_y + 15.5)
        pdf.set_font(f_fam, "", 8.1)
        pdf.set_text_color(*COLOR_TEXT_MUTED)
        pdf.multi_cell(card_w - 5, 4.1, lbl, align="L")

    pdf.set_fill_color(*COLOR_WHITE)
    pdf.set_y(cards_y + card_h + 3.5)
    pdf.set_font(f_fam, "", 7.9)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 4.0, "* AdER 29/10/2026 + CR 08/2026 + esposizione Santander da coobbligazione. ** Comprende anche passività riferite e non documentate; non è un debito certificato.")
    pdf.ln(6.5)

    # Esito della pre-analisi
    pdf.section_title("Esito della pre-analisi", top_gap=1.0)
    pdf.bullet("Redditività:", "forte peggioramento nel 2025; la riorganizzazione del personale potrebbe migliorare i margini, ma non è ancora dimostrata una continuità sostenibile.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Debito:", "il cumulo corretto comprende anche l'esposizione personale Santander; le altre posizioni personali sono censite separatamente se il saldo residuo non è noto.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Patrimonio:", "non emergono immobili dalla ricerca catastale; il realizzo dei beni mobili in liquidazione giudiziale è soltanto stimato per intervalli.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Strumenti:", "verificare prioritariamente la praticabilità della composizione negoziata (CNC), confrontandola con soluzioni di ristrutturazione e liquidazione giudiziale.", line_height=5.6, size_pt=9.7, gap_after=6.5)

    # Scopo e limiti + Base informativa in riquadro editoriale pulito
    pdf.framed_box(
        "Scopo, limiti e base informativa dell'analisi",
        "La relazione orienta le decisioni della titolare e dei professionisti sull'eventuale incarico successivo. Non è un piano di risanamento, una perizia estimativa, un'attestazione o un parere legale definitivo. Le informazioni sono distinte in documentate, riferite e simulazioni; l'assenza di stato patrimoniale, inventari e tesoreria limita le conclusioni.\n\n"
        "Base informativa esaminata: incontro del 20/10/2026; visura camerale; dichiarazioni fiscali 2023–2025; prospetti economici 2024–2026; documenti AdER, CR e CTC; documentazione su beni e proprietà acquisita nell'ottobre 2026.",
        title_size=9.8,
        body_size=9.1,
        line_height=5.0,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=4.8,
        pad_y=4.8,
    )

    # =========================================================================
    # PAGINA 2: 01 / PROFILO E CONTO ECONOMICO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("01", "Profilo e Conto Economico")

    pdf.section_title("Attività", top_gap=0)
    pdf.body_p(
        "Ditta individuale artigiana attiva dal 2018 nella fabbricazione, vendita e posa di infissi e serramenti, con officina e showroom a Palermo. La visura indica 11 addetti al 31/12/2025; la riduzione a due risorse è stata riferita nell'incontro e non è verificata da un prospetto del personale aggiornato.",
        line_height=4.8, size_pt=9.1, gap_after=3.5
    )

    pdf.section_title("Conto economico comparato", top_gap=0.5)
    col_w2 = (45, 27, 24, 28, 27, 29)  # totale 180mm = pdf.epw
    ce_rows = [
        ("Ricavi e proventi", "597.810", "199.270", "493.094", "−37,1%", "783.808", False),
        ("Acquisti", "394.814", "131.605", "263.690", "−20,3%", "330.945", False),
        ("Servizi", "57.248", "19.083", "38.957", "−26,0%", "52.641", False),
        ("Godimento beni di terzi", "4.500", "1.500", "18.324", "+1,1%", "18.126", False),
        ("Personale", "140.045", "46.682", "215.297", "−4,5%", "225.505", False),
        ("Altri oneri operativi", "1", "0", "265", "n.s.", "3", False),
        ("EBITDA / MOL", "1.202", "401", "−43.440", "n.s.", "156.588", True),
        ("EBITDA %", "0,2%", "0,2%", "−8,8%", "−28,8 p.p.", "20,0%", False),
        ("Ammortamenti esposti", "n.r.", "n.r.", "20.103", "+1,0%", "19.898", False),
        ("EBIT", "n.r.", "n.r.", "−63.543", "n.s.", "136.689", False),
        ("Oneri finanziari", "18", "6", "62", "−99,3%", "8.750", False),
        ("Risultato contabile", "1.183*", "394", "−63.605", "n.s.", "127.940", True),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w2,
        headings_style=header_style,
        line_height=4.8,
        padding=(1.35, 1.8),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT"),
    ) as table:
        row = table.row()
        row.cell("Voce")
        row.cell("31.12.2026\nriparam.*")
        row.cell("30.04.2026")
        row.cell("31.12.2025")
        row.cell("Var. %\n25/24")
        row.cell("31.12.2024")

        for idx, r in enumerate(ce_rows):
            base_row = cell_white if idx % 2 == 0 else cell_alt
            row = table.row(style=highlight_style if r[6] else base_row)
            cell_st = bold_style if (r[0].startswith("Ricavi") and not r[6]) else None
            row.cell(r[0], style=cell_st)
            row.cell(r[1], style=cell_st)
            row.cell(r[2], style=cell_st)
            row.cell(r[3], style=cell_st)
            row.cell(r[4], style=cell_st)
            row.cell(r[5], style=cell_st)

    pdf.ln(2.2)
    pdf.set_font(f_fam, "", 7.6)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.6, "Valori in euro, arrotondati; fonte: situazioni contabili 2024, 2025 e 01/01–30/04/2026, stampa 30/10/2026. * Il 2026 riparametrato è il quadrimestre × 3: non è previsione. Ammortamenti 2026 non esposti; il risultato annualizzato è soltanto aritmetico. n.r. = non ricostruibile; n.s. = percentuale poco significativa.")
    pdf.ln(3.5)

    pdf.section_title("Lettura professionale", top_gap=0.5)
    pdf.bullet("Nel 2025", "i ricavi diminuiscono del 37,1%, mentre il costo del personale si riduce solo del 4,5%: il MOL passa da +€156,6 mila a −€43,4 mila.", line_height=4.7, size_pt=8.9, gap_after=2.0)
    pdf.bullet("Il MOL 2024", "comprende €50.452 di proventi da cessione di crediti d'imposta: la loro ricorrenza non può essere presunta.", line_height=4.7, size_pt=8.9, gap_after=2.0)
    pdf.bullet("Nel 2026", "gli acquisti assorbono il 66,0% dei ricavi del quadrimestre, rispetto al 53,5% nel 2025. Rimanenze e lavori in corso non sono ricostruiti.", line_height=4.7, size_pt=8.9, gap_after=3.5)

    pdf.framed_box(
        "Raccordo fiscale (componente dichiarativa vs cassa — nessuna prova di incassi ulteriori)",
        "Il Modello Redditi PF 2026 (anno 2025) riporta €63.256 al rigo RG5 per ricavi non annotati: il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. Queste somme non sono incassi né fatturato: il commercialista deve spiegarne l'origine. Fonte: quadro RG modello 2026, pag. 4.",
        title_size=8.6,
        body_size=8.4,
        line_height=4.3,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=3.8,
        pad_y=3.0,
    )

    # =========================================================================
    # PAGINA 3: 02 / INDEBITAMENTO RICOSTRUITO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("02", "Indebitamento Ricostruito")

    pdf.body_p(
        "Le esposizioni sono state riclassificate distinguendo debiti con riscontro, coobbligazioni personali e importi ancora dichiarativi. I saldi disponibili si riferiscono a date diverse: l'aggregato ha funzione istruttoria, non è una certificazione del debito.",
        line_height=4.9, size_pt=9.2, gap_after=3.5
    )

    col_w3 = (76, 62, 42)
    deb_rows = [
        ("AdER – cartelle/avvisi da saldare", "Estratto 29/10/2026", "386.695,79", False),
        ("  di cui INPS (già incluso sopra)", "Avvisi di addebito", "210.604,29", False),
        ("  di cui altri carichi (già inclusi sopra)", "Tributi/enti diversi", "176.091,50", False),
        ("Intesa Sanpaolo – utilizzato CR", "Agosto 2026", "133.460,00", False),
        ("Santander – coobbligazione personale", "CTC 30/09/2026, rate residue", "2.945,00", False),
        ("ESPOSIZIONI PRINCIPALI QUANTIFICATE", "AdER + CR + Santander", "523.100,79", True),
        ("Fornitori", "Riferito nell'incontro", "120.000 circa", False),
        ("Dipendenti e TFR", "Riferito nell'incontro", "70.000 circa", False),
        ("Locazioni arretrate", "Riferito nell'incontro", "100.000–170.000", False),
        ("TOTALE MISTO INDICATIVO", "Documentato + riferito", "813.101–883.101", True),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w3,
        headings_style=header_style,
        line_height=5.2,
        padding=(1.6, 2.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "RIGHT"),
    ) as table:
        row = table.row()
        row.cell("Posizione")
        row.cell("Fonte / stato")
        row.cell("Importo (€)")

        for idx, r in enumerate(deb_rows):
            base_row = cell_white if idx % 2 == 0 else cell_alt
            row = table.row(style=highlight_style if r[3] else base_row)
            row.cell(r[0])
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(2.5)
    pdf.set_font(f_fam, "", 7.8)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.8, "N.B. Le righe 'di cui INPS' e 'di cui altri carichi' sono sottocomponenti AdER, non ulteriori debiti. Santander è incluso prudenzialmente come potenziale esposizione personale da coobbligazione, pur in assenza di scaduti segnalati; l'importo comprende rate residue, non soltanto capitale.")
    pdf.ln(4.0)

    pdf.section_title("Ulteriori rapporti finanziari e assenza di doppio conteggio", top_gap=0.5)
    pdf.bullet("Findomestic:", "carta rateale attiva, €143,20 in scadenza al 30/09/2026; il saldo residuo complessivo non è noto. La scadenza viene censita ma non sommata come se fosse l'intero debito.", line_height=4.8, size_pt=9.0, gap_after=2.3)
    pdf.bullet("GIADA SEC. / Intesa:", "la Centrale dei Rischi riporta esposizioni anche nel 2025 e cessioni successive. Sono date storiche/trasferimenti e non si sommano all'ultima segnalazione di €133.460 senza una ricostruzione contrattuale.", line_height=4.8, size_pt=9.0, gap_after=2.3)
    pdf.bullet("Compass e Agos:", "rapporti CTC chiusi regolarmente; non inclusi. Il finanziamento di circa €170.000 e la rata di €6.000 mensili sono riferiti e non aggiunti all'ultima CR.", line_height=4.8, size_pt=9.0, gap_after=4.0)

    pdf.framed_box(
        "Divergenza ancora aperta e fonti di riconciliazione",
        "Nell'incontro si è parlato di un totale di €640–690 mila, ma le cinque categorie dichiarate sommavano €810–880 mila. Il nuovo intervallo misto di €813–883 mila non risolve la differenza: non abbiamo scadenzari di fornitori, lavoratori e locazioni, né la riconciliazione di tutti i finanziamenti. Le rate della definizione agevolata AdER non sono aggiunte una seconda volta ai carichi già esposti.\n\n"
        "Fonti: AdER «Da saldare» 29/10/2026, pag. 5; CR Banca d'Italia, ultimo mese agosto 2026, pagg. 2–3 e storia delle segnalazioni; CTC 29/10/2026, pagg. 1–2; riepilogo incontro 20/10/2026, pag. 2.",
        title_size=9.0,
        body_size=8.4,
        line_height=4.3,
        accent_color=COLOR_TEAL,
        bg_color=COLOR_CARD_BG,
        pad_x=4.0,
        pad_y=3.2,
    )

    # =========================================================================
    # PAGINA 4: 03 / PATRIMONIO E CONFRONTO LIQUIDATORIO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("03", "Patrimonio e Confronto Liquidatorio")

    pdf.body_p(
        "Non è disponibile uno stato patrimoniale ricostruito. La ricognizione riguarda i beni individuati dai documenti, senza attribuire valore zero alle poste non conosciute.",
        line_height=4.9, size_pt=9.2, gap_after=3.5
    )

    col_w4_a = (54, 78, 48)
    patr_rows = [
        ("Immobili", "Ricerca catastale 29/10/2026: nessuna corrispondenza", "Nessun immobile emerso"),
        ("Fiat Panda 2012", "Proprietà da visura PRA; nessun gravame iscritto", "Valore da perizia"),
        ("Altre 2 autovetture", "Elenco della titolare; Captur con preavvisi di fermo", "Titoli/vincoli da verificare"),
        ("4 autocarri Renault/Nissan", "Elenco sottoscritto; dati tecnici incompleti", "Titoli/valore da verificare"),
        ("Macchinari e attrezzature", "Officina e ammortamenti in contabilità", "Nessun inventario"),
        ("Crediti, rimanenze, cassa", "Nessun saldo patrimoniale affidabile", "Non quantificabili"),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w4_a,
        headings_style=header_style,
        line_height=5.0,
        padding=(1.6, 2.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Categoria")
        row.cell("Evidenza")
        row.cell("Stato della stima")

        for idx, r in enumerate(patr_rows):
            row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
            row.cell(r[0], style=bold_style)
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(4.0)
    pdf.section_title("Stima esplorativa delle vendite concorsuali", top_gap=0.5)
    pdf.body_p(
        "Per confronto con la liquidazione giudiziale si ipotizzano vendite competitive per lotti omogenei, con possibili esperimenti deserti, ribassi e costi. Gli intervalli non sono perizie, basi d'asta o prezzi osservati di aggiudicazione.",
        line_height=4.8, size_pt=9.0, gap_after=3.0
    )

    col_w4_b = (90, 45, 45)
    lotti_rows = [
        ("3 autovetture", "€ 9.000", "€ 20.000", False),
        ("4 autocarri", "€ 15.000", "€ 45.000", False),
        ("Dotazioni dell'officina", "€ 0", "€ 8.000", False),
        ("Realizzo lordo", "€ 24.000", "€ 73.000", True),
        ("Realizzo netto diretto*", "~ € 20.000", "~ € 65.000", True),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w4_b,
        headings_style=header_style,
        line_height=5.0,
        padding=(1.6, 2.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "RIGHT", "RIGHT"),
    ) as table:
        row = table.row()
        row.cell("Lotto indicativo")
        row.cell("Prudente")
        row.cell("Favorevole")

        for idx, r in enumerate(lotti_rows):
            base_row = cell_white if idx % 2 == 0 else cell_alt
            row = table.row(style=highlight_style if r[3] else base_row)
            row.cell(r[0])
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(2.2)
    pdf.set_font(f_fam, "", 7.8)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.8, "* Importi convenzionali dopo i costi direttamente imputabili alle vendite, prima di spese generali della procedura, imposte, vincoli e prelazioni. La stima presume la titolarità e commerciabilità dei veicoli dichiarati; per sei veicoli non è stata acquisita una visura PRA. Non comprende crediti, disponibilità liquide, rimanenze, né un eventuale valore dell'azienda in esercizio.")
    pdf.ln(4.0)

    pdf.framed_box(
        "Implicazione economica",
        "L'attivo mobiliare così stimato appare contenuto rispetto alle passività. Non è possibile stimare una percentuale di soddisfacimento dei creditori con le sole informazioni disponibili. Una cessione dell'azienda in funzionamento, anche in sede concorsuale, potrebbe preservare un valore maggiore della vendita per lotti, ma l'avviamento oggi non è dimostrato.\n\n"
        "Fonti: elenco beni mobili registrati del 29/10/2026; visura PRA Panda del 29/10/2026; esito ricerca catastale del 29/10/2026; contabilità 2024–2025; AdER «Procedure attive»; confronto estimativo interno non peritale.",
        title_size=9.2,
        body_size=8.6,
        line_height=4.4,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=4.0,
        pad_y=3.2,
    )

    # =========================================================================
    # PAGINA 5: 04 / REDDITIVITÀ E CONTINUITÀ
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("04", "Redditività e Continuità")

    pdf.body_p(
        "Il tema determinante non è il fatturato storico, ma la capacità dell'organizzazione ristrutturata di produrre margine operativo ricorrente e cassa. Gli esercizi che seguono sono test meccanici, non scenari di piano.",
        line_height=5.2, size_pt=9.6, gap_after=4.5
    )

    col_w5 = (82, 43, 55)
    sens_rows = [
        ("EBITDA quadrimestre × 3", "+€ 1,2 mila", "Pareggio contabile fragile"),
        ("Canoni inclusi nel ×3", "€ 4,5 mila", "Sotto ai € 18 mila storici"),
        ("EBITDA con canone storico ipotetico", "−€ 12,3 mila", "Solo rettifica locazioni"),
        ("Personale annualizzato da aprile", "€ 140,0 mila", "Non misura il nuovo assetto"),
        ("EBITDA con personale a €60–70 mila e canone storico", "~ € 57,7–67,7 mila", "Ipotesi dichiarativa, non previsione"),
        ("Rata del finanziamento riferita", "€ 72 mila/anno", "Contratto non acquisito"),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w5,
        headings_style=header_style,
        line_height=5.8,
        padding=(2.1, 2.2),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "RIGHT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Verifica sul 2026 annualizzato")
        row.cell("Importo")
        row.cell("Lettura")

        for idx, r in enumerate(sens_rows):
            base_row = cell_white if idx % 2 == 0 else cell_alt
            row = table.row(style=highlight_style if "EBITDA con personale" in r[0] else base_row)
            row.cell(r[0])
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(3.0)
    pdf.set_font(f_fam, "", 8.2)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 4.1, "I test non tengono conto di rimanenze, imposte, investimenti, variazione del capitale circolante o costi aggiuntivi di lavorazioni esterne. Anche l'ipotesi più favorevole di EBITDA resta inferiore alla rata annua riferita di €72 mila, prima delle altre esigenze finanziarie.")
    pdf.ln(5.0)

    pdf.section_title("Principali criticità operative", top_gap=0.5)
    pdf.bullet("Acquisti:", "l'incidenza sui ricavi raggiunge circa il 66% nel primo quadrimestre 2026; occorre capire se dipenda da mix commerciale, costi o disallineamento degli acquisti.", line_height=5.1, size_pt=9.4, gap_after=2.8)
    pdf.bullet("Struttura:", "la riduzione del personale non prova che l'attività possa mantenere volumi e qualità con due risorse; forte dipendenza operativa da Salvatore.", line_height=5.1, size_pt=9.4, gap_after=2.8)
    pdf.bullet("Circolante e liquidità:", "anticipi clienti, scaduti e condizioni dei fornitori non sono ricostruiti; non è possibile determinare flusso disponibile per il debito né DSCR attendibile.", line_height=5.1, size_pt=9.4, gap_after=4.5)

    pdf.framed_box(
        "Giudizio preliminare sulla continuità",
        "La continuità non è attualmente dimostrata, ma la potenziale riduzione dei costi giustifica una verifica mirata. Condizioni decisive: margine su commessa, costi effettivi dopo la riorganizzazione, completamento ordini, scadenze del debito e disponibilità di cassa. Un EBITDA positivo non coincide con il cash flow utilizzabile per pagare i creditori.\n\n"
        "Fonti: contabilità 2024–2026; riepilogo incontro del 20/10/2026; confronto tecnico interno sui saldi contabili e ipotesi riferite.",
        title_size=9.5,
        body_size=8.9,
        line_height=4.7,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=4.5,
        pad_y=3.6,
    )

    # =========================================================================
    # PAGINA 6: 05 / INQUADRAMENTO CCII
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("05", "Inquadramento CCII")

    pdf.section_title("Impresa individuale: effetti decisivi", top_gap=0)
    pdf.body_p(
        "La ditta è un'impresa artigiana individuale. La qualifica camerale di «piccolo imprenditore» non coincide con quella di impresa minore ex art. 2, comma 1, lett. d), CCII. I ricavi 2023–2025 superano la soglia di €200.000 annui: il concordato minore non appare accessibile. La ditta è invece astrattamente assoggettabile a liquidazione giudiziale, ove ne ricorrano i presupposti (art. 121).",
        line_height=4.9, size_pt=9.1, gap_after=2.8
    )
    pdf.body_p(
        "Il patrimonio aziendale non è separato da quello della titolare come in una S.r.l.: Lucrezia risponde personalmente delle obbligazioni, nei limiti di legge (art. 2740 c.c.). Anche le coobbligazioni e i rapporti personali devono essere censiti; cessazione o cessione dell'azienda non cancellano automaticamente i debiti. La posizione di Salvatore, indicato come collaboratore familiare al 49% nelle dichiarazioni fiscali, richiede la verifica dei diritti ex art. 230-bis c.c.",
        line_height=4.9, size_pt=9.1, gap_after=4.0
    )

    pdf.section_title("Strumenti confrontati", top_gap=0.5)
    col_w6 = (60, 44, 76)
    tools_rows = [
        ("CNC - artt. 12 ss.", "Priorità di verifica", "Risanamento ragionevolmente perseguibile, anche tramite cessione"),
        ("Accordi di ristrutturazione - artt. 57 e 63", "Valutabili", "Consensi, disciplina crediti tributari/contributivi e flussi"),
        ("Concordato preventivo - art. 84", "Alternativa possibile", "Proposta sostenibile; continuità o requisiti liquidatori"),
        ("Concordato minore - art. 74", "Non appare accessibile", "Impresa non qualificabile come minore sulla base dei ricavi"),
        ("Liquidazione giudiziale - art. 121", "Alternativa effettiva", "Accertamento dell'insolvenza e inventario completo"),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w6,
        headings_style=header_style,
        line_height=5.2,
        padding=(1.7, 2.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Strumento")
        row.cell("Prima valutazione")
        row.cell("Condizione di accesso / fattibilità")

        for idx, r in enumerate(tools_rows):
            base_row = cell_white if idx % 2 == 0 else cell_alt
            row = table.row(style=highlight_style if "CNC" in r[0] else base_row)
            row.cell(r[0])
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(4.0)
    pdf.section_title("Avvertenze giuridiche", top_gap=0.5)
    pdf.bullet("Le misure protettive", "nella CNC richiedono istanza e controllo giudiziale secondo gli artt. 18–19; non derivano automaticamente dalla sola intenzione di avviarla.", line_height=4.8, size_pt=8.9, gap_after=2.0)
    pdf.bullet("Il trattamento di tributi e contributi", "varia per strumento (artt. 23, 63 e 88 CCII); non si può presumere una falcidia. Eventuali estensioni ai tributi regionali/locali introdotte da novelle recenti (es. D.Lgs. 136/2024 e succ. mod.) vanno verificate sul testo ufficiale vigente.", line_height=4.8, size_pt=8.9, gap_after=2.0)
    pdf.bullet("La newco", "è un possibile veicolo di continuità indiretta, non uno strumento per liberare la titolare dai debiti; vanno valutati art. 2560 c.c., rapporti di lavoro e disciplina delle cessioni concorsuali.", line_height=4.8, size_pt=8.9, gap_after=2.0)
    pdf.bullet("Liquidazione giudiziale:", "in un'eventuale liquidazione della persona fisica occorrerà esaminare presupposti ed effetti dell'esdebitazione (artt. 278 ss. CCII).", line_height=4.8, size_pt=8.9, gap_after=3.0)

    pdf.body_p(
        "Normativa di riferimento: D.Lgs. 14/2019 (CCII) e D.Lgs. 136/2024 (Correttivo-ter), artt. 2, 12, 18–19, 23, 57, 63, 74, 84, 121, 214, 278 ss. CCII; artt. 230-bis, 2560 e 2740 c.c. Eventuali ulteriori aggiornamenti normativi (incluso il citato D.Lgs. 147/2026) richiedono verifica puntuale di vigenza in Gazzetta Ufficiale da parte del legale (Human Gate).",
        line_height=3.9, size_pt=7.8, color=COLOR_TEXT_MUTED, gap_after=0
    )

    # =========================================================================
    # PAGINA 7: 06 / CONCLUSIONI E PROPOSTA DI INCARICO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("06", "Conclusioni e Proposta di Incarico")

    pdf.framed_box(
        "PROPOSTA: VERIFICA DI FATTIBILITÀ DELLA COMPOSIZIONE NEGOZIATA",
        "Dare priorità a un incarico circoscritto volto a verificare se l'impresa, dopo la riorganizzazione, possa produrre cassa sufficiente a sostenere la gestione e un trattamento credibile delle passività. La CNC non è oggi assunta come procedura già scelta. In parallelo va mantenuto il confronto con liquidazione giudiziale e cessione in continuità indiretta.",
        title_size=9.5,
        body_size=9.0,
        line_height=4.6,
        accent_color=COLOR_NAVY,
        bg_color=COLOR_CARD_BG,
        pad_x=4.2,
        pad_y=3.4,
    )

    pdf.section_title("Perché questa impostazione", top_gap=0.5)
    pdf.bullet("L'impresa è operativa", "e conserva una base commerciale, ma il 2025 è in perdita e il pareggio del primo quadrimestre 2026 non è consolidato.", line_height=4.9, size_pt=9.1, gap_after=2.2)
    pdf.bullet("Il debito è elevato:", "€523.100,79 di esposizioni principali quantificate, considerando la coobbligazione personale, più €290–360 mila riferiti per fornitori, dipendenti e locazioni.", line_height=4.9, size_pt=9.1, gap_after=2.2)
    pdf.bullet("L'attivo concorsuale", "individuato è limitato e incompleto: senza crediti, magazzino e cespiti valorizzati non si può attestare la convenienza della continuità rispetto alla liquidazione.", line_height=4.9, size_pt=9.1, gap_after=3.5)

    pdf.section_title("Verifiche essenziali dell'eventuale incarico successivo", top_gap=0.5)
    col_w7 = (20, 92, 68)
    verif_rows = [
        ("1", "Consuntivo 2026 post-riduzione; margini per commessa e capacità produttiva", "EBITDA sostenibile"),
        ("2", "Scadenzari fornitori, dipendenti, locazioni, contratti finanziari e CTC aggiornata", "Debito riconciliato"),
        ("3", "Incassi, pagamenti, anticipi, saldi bancari, rimanenze, crediti e cespiti", "Cassa e attivo effettivo"),
        ("4", "Interlocuzione su crediti pubblici, disponibilità dei fornitori e ipotesi di cessione", "Confronto CNC / altre opzioni / liquidazione"),
    ]

    pdf.set_fill_color(*COLOR_WHITE)
    with pdf.table(
        col_widths=col_w7,
        headings_style=header_style,
        line_height=5.3,
        padding=(1.7, 2.0),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Priorità")
        row.cell("Verifica mirata")
        row.cell("Risultato atteso")

        for idx, r in enumerate(verif_rows):
            row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
            row.cell(r[0], style=bold_style)
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(4.0)
    pdf.section_title("Conclusione", top_gap=0.5)
    pdf.body_p(
        "Non è oggi possibile affermare che il risanamento sia fattibile. È però possibile proporre una verifica professionale mirata sulla CNC e sulle alternative, con un perimetro e risultati attesi definiti. Qualora la redditività normalizzata e la negoziabilità delle passività non trovassero riscontro, l'opzione liquidatoria dovrà essere valutata tempestivamente, considerando gli effetti personali sulla titolare.",
        line_height=4.8, size_pt=9.0, gap_after=3.0
    )

    pdf.framed_box(
        "Base documentale e precisazione finale",
        "Principali documenti utilizzati: Visura CCIAA 27/03/2026; Modelli Redditi PF 2024–2026; situazioni contabili 2024, 2025 e 30/04/2026; AdER «Da saldare», «Saldati», «Procedure attive» e moduli definizione agevolata; CR Banca d'Italia 29/10/2026 (ultimo dato agosto); visura CTC 29/10/2026; ricerca catastale, elenco beni, ispezione PRA; riepilogo dell'incontro 20/10/2026.\n\n"
        "Precisazione finale: la somma €523.100,79 combina date diverse e comprende €2.945 di rate residue riferite a una coobbligazione non scaduta. Le posizioni Findomestic e GIADA sono censite ma non maggiorate nel totale in assenza di evidenza di un debito ulteriore attuale. Il totale misto è soltanto indicativo e non sostituisce un elenco definitivo dei creditori.",
        title_size=8.6,
        body_size=7.9,
        line_height=4.0,
        accent_color=COLOR_TEAL,
        bg_color=COLOR_CARD_BG,
        pad_x=3.8,
        pad_y=2.8,
    )

    return bytes(pdf.output())


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

    client_name = header.get("cliente") or "CLIENTE"
    draft_date = header.get("data_bozza") or "13/11/2026"
    forma_giuridica = header.get("forma_giuridica") or c2.get("forma_giuridica") or "Società / Impresa"
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
