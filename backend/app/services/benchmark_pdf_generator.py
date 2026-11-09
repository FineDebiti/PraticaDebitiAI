"""Generatore del Benchmark PDF di Preanalisi a 7 Pagine (DossierLex).

Riproduce fedelmente la struttura, la densità, la tavolozza e il rigore peritale del documento:
'Preanalisi_Definitiva_Lucrezia_DAmico_09-11-2026.pdf' (7 pagine esatte).
"""

import os
from typing import Dict, Any, List, Optional
from fpdf import FPDF
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode, TableBordersLayout, XPos, YPos

# Tavolozza peritale DossierLex Benchmark
COLOR_NAVY = (16, 42, 67)         # #102a43 Titoli e intestazioni primarie
COLOR_TEAL = (2, 132, 199)        # #0284c7 Capitoli (01 / PROFILO...)
COLOR_SUBTITLE = (71, 85, 105)    # #475569 Sottotitoli
COLOR_TEXT_DARK = (30, 41, 59)    # #1e293b Testo principale ad alto contrasto
COLOR_TEXT_MUTED = (100, 116, 139)# #64748b Testo secondario e note
COLOR_BORDER = (203, 213, 225)    # #cbd5e1 Bordi tabelle e card
COLOR_CARD_BG = (248, 250, 252)   # #f8fafc Sfondo card
COLOR_ROW_ALT = (241, 245, 249)   # #f1f5f9 Righe evidenziate
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
    """FPDF specializzata per il report cliente a 7 pagine esatte."""

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
        self.set_y(-12)
        self.set_font(self.font_family_name, "", 7.5)
        self.set_text_color(*COLOR_TEXT_MUTED)

        # Sinistra
        left_text = f"PRE-ANALISI CRISI D'IMPRESA | {self.client_name.upper()}"
        self.cell(self.epw / 2, 4, left_text, align="L")

        # Destra: RISERVATO • 09.11.2026 • 1 / 7
        right_text = f"RISERVATO • {self.draft_date} • {self.page_no()} / {{nb}}"
        self.cell(self.epw / 2, 4, right_text, align="R")

    def page_top_breadcrumb(self, chapter_code: str, chapter_title: str):
        """Intestazione standard per le pagine 2-7."""
        self.set_xy(15, 14)
        self.set_font(self.font_family_name, "", 7.5)
        self.set_text_color(*COLOR_TEXT_MUTED)
        self.cell(self.epw, 4, "RELAZIONE DI PRE-ANALISI / VERSIONE DEFINITIVA", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(1)
        self.set_font(self.font_family_name, "B", 10.5)
        self.set_text_color(*COLOR_TEAL)
        self.cell(self.epw, 5, f"{chapter_code} / {chapter_title.upper()}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(3)

    def section_title(self, title: str):
        """Titolo di sezione (es. 'Attività', 'Conto economico comparato')."""
        self.set_font(self.font_family_name, "B", 9.5)
        self.set_text_color(*COLOR_NAVY)
        self.cell(self.epw, 4.5, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(1.2)

    def body_p(self, text: str, line_height: float = 4.0, size_pt: float = 8.0, color=COLOR_TEXT_DARK):
        self.set_font(self.font_family_name, "", size_pt)
        self.set_text_color(*color)
        self.multi_cell(self.epw, line_height, text, align="L")
        self.ln(1.5)

    def bullet(self, bold_prefix: str, text: str, line_height: float = 3.8, size_pt: float = 7.8):
        self.set_font(self.font_family_name, "B", size_pt)
        self.set_text_color(*COLOR_TEXT_DARK)
        prefix = f"• {bold_prefix} " if bold_prefix else "• "
        pw = self.get_string_width(prefix)
        self.write(line_height, prefix)

        self.set_font(self.font_family_name, "", size_pt)
        self.write(line_height, text)
        self.ln(line_height + 0.8)


def generate_benchmark_7page_pdf(report_data: Dict[str, Any]) -> bytes:
    """Costruisce il PDF di 7 pagine peritali conforme al benchmark."""
    header = report_data.get("header", {})
    client_name = header.get("cliente") or "LUCREZIA D'AMICO"
    draft_date = header.get("data_bozza") or "09.11.2026"
    forma_giuridica = header.get("forma_giuridica") or "Ditta individuale artigiana · Palermo"

    # FontFace per tabelle
    pdf = BenchmarkPreanalysisPDF(client_name=client_name, draft_date=draft_date)
    f_fam = pdf.font_family_name

    header_style = FontFace(family=f_fam, emphasis="B", size_pt=7.5, color=COLOR_WHITE, fill_color=COLOR_NAVY)
    bold_style = FontFace(family=f_fam, emphasis="B", size_pt=7.5, color=COLOR_TEXT_DARK, fill_color=COLOR_WHITE)
    highlight_style = FontFace(family=f_fam, emphasis="B", size_pt=7.5, color=COLOR_NAVY, fill_color=COLOR_ROW_ALT)

    # =========================================================================
    # PAGINA 1: COPERTINA ED EXECUTIVE SUMMARY
    # =========================================================================
    pdf.add_page()
    pdf.set_y(14)
    pdf.set_font(f_fam, "B", 7.5)
    pdf.set_text_color(*COLOR_TEAL)
    pdf.cell(pdf.epw, 4, f"RELAZIONE FINALE DI PRE-ANALISI | {draft_date.upper()}", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    pdf.set_font(f_fam, "B", 18)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw, 7.5, "Crisi d'impresa", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(pdf.epw, 7.5, client_name, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    pdf.set_font(f_fam, "", 9)
    pdf.set_text_color(*COLOR_SUBTITLE)
    pdf.cell(pdf.epw, 4.5, forma_giuridica, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(pdf.epw, 4.5, "Ricostruzione economico-finanziaria, debitoria e prima valutazione degli strumenti CCII", align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # 4 Card metriche chiave
    cards_y = pdf.get_y()
    card_w = (pdf.epw - 9) / 4  # 4 card con 3 gap da 3mm
    card_h = 24

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

        pdf.set_xy(cx + 2, cards_y + 4)
        pdf.set_font(f_fam, "B", 11)
        pdf.set_text_color(*COLOR_NAVY)
        pdf.cell(card_w - 4, 5, val, align="L")

        pdf.set_xy(cx + 2, cards_y + 11)
        pdf.set_font(f_fam, "", 7)
        pdf.set_text_color(*COLOR_TEXT_MUTED)
        pdf.multi_cell(card_w - 4, 3.5, lbl, align="L")

    pdf.set_y(cards_y + card_h + 2)
    pdf.set_font(f_fam, "", 6.5)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.2, "* AdER 29/10/2026 + CR 08/2026 + esposizione Santander da coobbligazione. ** Comprende anche passività riferite e non documentate; non è un debito certificato.")
    pdf.ln(3)

    # Esito della pre-analisi
    pdf.section_title("Esito della pre-analisi")
    pdf.bullet("Redditività:", "forte peggioramento nel 2025; la riorganizzazione del personale potrebbe migliorare i margini, ma non è ancora dimostrata una continuità sostenibile.")
    pdf.bullet("Debito:", "il cumulo corretto comprende anche l'esposizione personale Santander; le altre posizioni personali sono censite separatamente se il saldo residuo non è noto.")
    pdf.bullet("Patrimonio:", "non emergono immobili dalla ricerca catastale; il realizzo dei beni mobili in liquidazione giudiziale è soltanto stimato per intervalli.")
    pdf.bullet("Strumenti:", "verificare prioritariamente la praticabilità della composizione negoziata (CNC), confrontandola con soluzioni di ristrutturazione e liquidazione giudiziale.")
    pdf.ln(2)

    # Scopo e limiti
    pdf.section_title("Scopo e limiti")
    pdf.body_p(
        "La relazione orienta le decisioni della titolare e dei professionisti sull'eventuale incarico successivo. Non è un piano di risanamento, una perizia estimativa, un'attestazione o un parere legale definitivo. Le informazioni sono distinte in documentate, riferite e simulazioni; l'assenza di stato patrimoniale, inventari e tesoreria limita le conclusioni.",
        line_height=3.8, size_pt=7.5
    )
    pdf.body_p(
        "Base informativa: incontro del 20/10/2026; visura camerale; dichiarazioni fiscali 2023–2025; prospetti economici 2024–2026; documenti AdER, CR e CTC; documentazione su beni e proprietà acquisita nell'ottobre 2026.",
        line_height=3.5, size_pt=7.0, color=COLOR_TEXT_MUTED
    )

    # =========================================================================
    # PAGINA 2: 01 / PROFILO E CONTO ECONOMICO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("01", "Profilo e Conto Economico")

    pdf.section_title("Attività")
    pdf.body_p(
        "Ditta individuale artigiana attiva dal 2018 nella fabbricazione, vendita e posa di infissi e serramenti, con officina e showroom a Palermo. La visura indica 11 addetti al 31/12/2025; la riduzione a due risorse è stata riferita nell'incontro e non è verificata da un prospetto del personale aggiornato.",
        line_height=3.8, size_pt=7.8
    )

    pdf.section_title("Conto economico comparato")
    col_w2 = (45, 27, 24, 28, 27, 29) # totale 180mm = pdf.epw
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

    with pdf.table(
        col_widths=col_w2,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
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

        for r in ce_rows:
            st = highlight_style if r[6] else bold_style if r[0].startswith("Ricavi") else None
            row = table.row()
            row.cell(r[0], style=st)
            row.cell(r[1], style=st)
            row.cell(r[2], style=st)
            row.cell(r[3], style=st)
            row.cell(r[4], style=st)
            row.cell(r[5], style=st)

    pdf.ln(1.5)
    pdf.set_font(f_fam, "", 6.5)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.0, "Valori in euro, arrotondati; fonte: situazioni contabili 2024, 2025 e 01/01–30/04/2026, stampa 30/10/2026. * Il 2026 riparametrato è il quadrimestre × 3: non è previsione. Ammortamenti 2026 non esposti; il risultato annualizzato è soltanto aritmetico. n.r. = non ricostruibile; n.s. = percentuale poco significativa.")
    pdf.ln(2.5)

    pdf.section_title("Lettura professionale")
    pdf.bullet("Nel 2025", "i ricavi diminuiscono del 37,1%, mentre il costo del personale si riduce solo del 4,5%: il MOL passa da +€156,6 mila a −€43,4 mila.")
    pdf.bullet("Il MOL 2024", "comprende €50.452 di proventi da cessione di crediti d'imposta: la loro ricorrenza non può essere presunta.")
    pdf.bullet("Nel 2026", "gli acquisti assorbono il 66,0% dei ricavi del quadrimestre, rispetto al 53,5% nel 2025. Rimanenze e lavori in corso non sono ricostruiti.")
    pdf.ln(2)

    # Box Raccordo fiscale
    box_y = pdf.get_y()
    pdf.set_fill_color(*COLOR_CARD_BG)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.rect(15, box_y, pdf.epw, 14, style="DF")
    pdf.set_xy(17, box_y + 2)
    pdf.set_font(f_fam, "B", 7.2)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.write(3.5, "Raccordo fiscale. ")
    pdf.set_font(f_fam, "", 7.2)
    pdf.set_text_color(*COLOR_TEXT_DARK)
    pdf.multi_cell(pdf.epw - 4, 3.5, "Il Modello Redditi PF 2026 (anno 2025) riporta €63.256 al rigo RG5 per ricavi non annotati: il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. Fonte: quadro RG del modello 2026, pag. 4.")

    # =========================================================================
    # PAGINA 3: 02 / INDEBITAMENTO RICOSTRUITO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("02", "Indebitamento Ricostruito")

    pdf.body_p(
        "Le esposizioni sono state riclassificate distinguendo debiti con riscontro, coobbligazioni personali e importi ancora dichiarativi. I saldi disponibili si riferiscono a date diverse: l'aggregato ha funzione istruttoria, non è una certificazione del debito.",
        line_height=3.8, size_pt=7.8
    )

    col_w3 = (75, 65, 40)
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

    with pdf.table(
        col_widths=col_w3,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "RIGHT"),
    ) as table:
        row = table.row()
        row.cell("Posizione")
        row.cell("Fonte / stato")
        row.cell("Importo (€)")

        for r in deb_rows:
            st = highlight_style if r[3] else None
            row = table.row()
            row.cell(r[0], style=st)
            row.cell(r[1], style=st)
            row.cell(r[2], style=st)

    pdf.ln(1.5)
    pdf.set_font(f_fam, "", 6.5)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.0, "N.B. Le righe 'di cui INPS' e 'di cui altri carichi' sono sottocomponenti AdER, non ulteriori debiti. Santander è incluso prudenzialmente come potenziale esposizione personale da coobbligazione, pur in assenza di scaduti segnalati; l'importo comprende rate residue, non soltanto capitale.")
    pdf.ln(2.5)

    pdf.section_title("Ulteriori rapporti finanziari e assenza di doppio conteggio")
    pdf.bullet("Findomestic:", "carta rateale attiva, €143,20 in scadenza al 30/09/2026; il saldo residuo complessivo non è noto. La scadenza viene censita ma non sommata come se fosse l'intero debito.")
    pdf.bullet("GIADA SEC. / Intesa:", "la Centrale dei Rischi riporta esposizioni anche nel 2025 e cessioni successive. Sono date storiche/trasferimenti e non si sommano all'ultima segnalazione di €133.460 senza una ricostruzione contrattuale.")
    pdf.bullet("Compass e Agos:", "rapporti CTC chiusi regolarmente; non inclusi. Il finanziamento di circa €170.000 e la rata di €6.000 mensili sono riferiti e non aggiunti all'ultima CR.")
    pdf.ln(2)

    pdf.section_title("Divergenza ancora aperta")
    pdf.body_p(
        "Nell'incontro si è parlato di un totale di €640–690 mila, ma le cinque categorie dichiarate sommavano €810–880 mila. Il nuovo intervallo misto di €813–883 mila non risolve la differenza: non abbiamo scadenzari di fornitori, lavoratori e locazioni, né la riconciliazione di tutti i finanziamenti. Le rate della definizione agevolata AdER non sono aggiunte una seconda volta ai carichi già esposti.",
        line_height=3.8, size_pt=7.5
    )
    pdf.body_p(
        "Fonti: AdER «Da saldare» 29/10/2026, pag. 5; CR Banca d'Italia, ultimo mese agosto 2026, pagg. 2–3 e storia delle segnalazioni; CTC 29/10/2026, pagg. 1–2; riepilogo incontro 20/10/2026, pag. 2.",
        line_height=3.2, size_pt=6.8, color=COLOR_TEXT_MUTED
    )

    # =========================================================================
    # PAGINA 4: 03 / PATRIMONIO E CONFRONTO LIQUIDATORIO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("03", "Patrimonio e Confronto Liquidatorio")

    pdf.body_p(
        "Non è disponibile uno stato patrimoniale ricostruito. La ricognizione riguarda i beni individuati dai documenti, senza attribuire valore zero alle poste non conosciute.",
        line_height=3.8, size_pt=7.8
    )

    col_w4_a = (55, 75, 50)
    patr_rows = [
        ("Immobili", "Ricerca catastale 29/10/2026: nessuna corrispondenza", "Nessun immobile emerso"),
        ("Fiat Panda 2012", "Proprietà da visura PRA; nessun gravame iscritto", "Valore da perizia"),
        ("Altre 2 autovetture", "Elenco della titolare; Captur con preavvisi di fermo", "Titoli/vincoli da verificare"),
        ("4 autocarri Renault/Nissan", "Elenco sottoscritto; dati tecnici incompleti", "Titoli/valore da verificare"),
        ("Macchinari e attrezzature", "Officina e ammortamenti in contabilità", "Nessun inventario"),
        ("Crediti, rimanenze, cassa", "Nessun saldo patrimoniale affidabile", "Non quantificabili"),
    ]

    with pdf.table(
        col_widths=col_w4_a,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Categoria")
        row.cell("Evidenza")
        row.cell("Stato della stima")

        for r in patr_rows:
            row = table.row()
            row.cell(r[0], style=bold_style)
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(2.5)
    pdf.section_title("Stima esplorativa delle vendite concorsuali")
    pdf.body_p(
        "Per confronto con la liquidazione giudiziale si ipotizzano vendite competitive per lotti omogenei, con possibili esperimenti deserti, ribassi e costi. Gli intervalli non sono perizie, basi d'asta o prezzi osservati di aggiudicazione.",
        line_height=3.6, size_pt=7.5
    )

    col_w4_b = (90, 45, 45)
    lotti_rows = [
        ("3 autovetture", "€ 9.000", "€ 20.000", False),
        ("4 autocarri", "€ 15.000", "€ 45.000", False),
        ("Dotazioni dell'officina", "€ 0", "€ 8.000", False),
        ("Realizzo lordo", "€ 24.000", "€ 73.000", True),
        ("Realizzo netto diretto*", "~ € 20.000", "~ € 65.000", True),
    ]

    with pdf.table(
        col_widths=col_w4_b,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "RIGHT", "RIGHT"),
    ) as table:
        row = table.row()
        row.cell("Lotto indicativo")
        row.cell("Prudente")
        row.cell("Favorevole")

        for r in lotti_rows:
            st = highlight_style if r[3] else None
            row = table.row()
            row.cell(r[0], style=st)
            row.cell(r[1], style=st)
            row.cell(r[2], style=st)

    pdf.ln(1.5)
    pdf.set_font(f_fam, "", 6.5)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.0, "* Importi convenzionali dopo i costi direttamente imputabili alle vendite, prima di spese generali della procedura, imposte, vincoli e prelazioni. La stima presume la titolarità e commerciabilità dei veicoli dichiarati; per sei veicoli non è stata acquisita una visura PRA. Non comprende crediti, disponibilità liquide, rimanenze, né un eventuale valore dell'azienda in esercizio.")
    pdf.ln(2.5)

    pdf.section_title("Implicazione economica")
    pdf.body_p(
        "L'attivo mobiliare così stimato appare contenuto rispetto alle passività. Non è possibile stimare una percentuale di soddisfacimento dei creditori con le sole informazioni disponibili. Una cessione dell'azienda in funzionamento, anche in sede concorsuale, potrebbe preservare un valore maggiore della vendita per lotti, ma l'avviamento oggi non è dimostrato.",
        line_height=3.8, size_pt=7.5
    )
    pdf.body_p(
        "Fonti: elenco beni mobili registrati del 29/10/2026; visura PRA Panda del 29/10/2026; esito ricerca catastale del 29/10/2026; contabilità 2024–2025; AdER «Procedure attive»; confronto estimativo interno non peritale.",
        line_height=3.2, size_pt=6.8, color=COLOR_TEXT_MUTED
    )

    # =========================================================================
    # PAGINA 5: 04 / REDDITIVITÀ E CONTINUITÀ
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("04", "Redditività e Continuità")

    pdf.body_p(
        "Il tema determinante non è il fatturato storico, ma la capacità dell'organizzazione ristrutturata di produrre margine operativo ricorrente e cassa. Gli esercizi che seguono sono test meccanici, non scenari di piano.",
        line_height=3.8, size_pt=7.8
    )

    col_w5 = (80, 45, 55)
    sens_rows = [
        ("EBITDA quadrimestre × 3", "+€ 1,2 mila", "Pareggio contabile fragile"),
        ("Canoni inclusi nel ×3", "€ 4,5 mila", "Sotto ai € 18 mila storici"),
        ("EBITDA con canone storico ipotetico", "−€ 12,3 mila", "Solo rettifica locazioni"),
        ("Personale annualizzato da aprile", "€ 140,0 mila", "Non misura il nuovo assetto"),
        ("EBITDA con personale a €60–70 mila e canone storico", "~ € 57,7–67,7 mila", "Ipotesi dichiarativa, non previsione"),
        ("Rata del finanziamento riferita", "€ 72 mila/anno", "Contratto non acquisito"),
    ]

    with pdf.table(
        col_widths=col_w5,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "RIGHT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Verifica sul 2026 annualizzato")
        row.cell("Importo")
        row.cell("Lettura")

        for r in sens_rows:
            st = highlight_style if "EBITDA con personale" in r[0] else None
            row = table.row()
            row.cell(r[0], style=st)
            row.cell(r[1], style=st)
            row.cell(r[2], style=st)

    pdf.ln(1.5)
    pdf.set_font(f_fam, "", 6.5)
    pdf.set_text_color(*COLOR_TEXT_MUTED)
    pdf.multi_cell(pdf.epw, 3.0, "I test non tengono conto di rimanenze, imposte, investimenti, variazione del capitale circolante o costi aggiuntivi di lavorazioni esterne. Anche l'ipotesi più favorevole di EBITDA resta inferiore alla rata annua riferita di €72 mila, prima delle altre esigenze finanziarie.")
    pdf.ln(2.5)

    pdf.section_title("Principali criticità operative")
    pdf.bullet("Acquisti:", "l'incidenza sui ricavi raggiunge circa il 66% nel primo quadrimestre 2026; occorre capire se dipenda da mix commerciale, costi o disallineamento degli acquisti.")
    pdf.bullet("Struttura:", "la riduzione del personale non prova che l'attività possa mantenere volumi e qualità con due risorse; forte dipendenza operativa da Salvatore.")
    pdf.bullet("Circolante e liquidità:", "anticipi clienti, scaduti e condizioni dei fornitori non sono ricostruiti; non è possibile determinare flusso disponibile per il debito né DSCR attendibile.")
    pdf.ln(2)

    pdf.section_title("Giudizio preliminare")
    pdf.body_p(
        "La continuità non è attualmente dimostrata, ma la potenziale riduzione dei costi giustifica una verifica mirata. Condizioni decisive: margine su commessa, costi effettivi dopo la riorganizzazione, completamento ordini, scadenze del debito e disponibilità di cassa. Un EBITDA positivo non coincide con il cash flow utilizzabile per pagare i creditori.",
        line_height=3.8, size_pt=7.5
    )
    pdf.body_p(
        "Fonti: contabilità 2024–2026; riepilogo incontro del 20/10/2026; confronto tecnico interno sui saldi contabili e ipotesi riferite.",
        line_height=3.2, size_pt=6.8, color=COLOR_TEXT_MUTED
    )

    # =========================================================================
    # PAGINA 6: 05 / INQUADRAMENTO CCII
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("05", "Inquadramento CCII")

    pdf.section_title("Impresa individuale: effetti decisivi")
    pdf.body_p(
        "La ditta è un'impresa artigiana individuale. La qualifica camerale di «piccolo imprenditore» non coincide con quella di impresa minore ex art. 2, comma 1, lett. d), CCII. I ricavi 2023–2025 superano la soglia di €200.000 annui: il concordato minore non appare accessibile. La ditta è invece astrattamente assoggettabile a liquidazione giudiziale, ove ne ricorrano i presupposti (art. 121).",
        line_height=3.8, size_pt=7.5
    )
    pdf.body_p(
        "Il patrimonio aziendale non è separato da quello della titolare come in una S.r.l.: Lucrezia risponde personalmente delle obbligazioni, nei limiti di legge (art. 2740 c.c.). Anche le coobbligazioni e i rapporti personali devono essere censiti; cessazione o cessione dell'azienda non cancellano automaticamente i debiti. La posizione di Salvatore, indicato come collaboratore familiare al 49% nelle dichiarazioni fiscali, richiede la verifica dei diritti ex art. 230-bis c.c.",
        line_height=3.8, size_pt=7.5
    )

    pdf.section_title("Strumenti confrontati")
    col_w6 = (60, 45, 75)
    tools_rows = [
        ("CNC - artt. 12 ss.", "Priorità di verifica", "Risanamento ragionevolmente perseguibile, anche tramite cessione"),
        ("Accordi di ristrutturazione - artt. 57 e 63", "Valutabili", "Consensi, disciplina crediti tributari/contributivi e flussi"),
        ("Concordato preventivo - art. 84", "Alternativa possibile", "Proposta sostenibile; continuità o requisiti liquidatori"),
        ("Concordato minore - art. 74", "Non appare accessibile", "Impresa non qualificabile come minore sulla base dei ricavi"),
        ("Liquidazione giudiziale - art. 121", "Alternativa effettiva", "Accertamento dell'insolvenza e inventario completo"),
    ]

    with pdf.table(
        col_widths=col_w6,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("LEFT", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Strumento")
        row.cell("Prima valutazione")
        row.cell("Condizione di accesso / fattibilità")

        for r in tools_rows:
            st = highlight_style if "CNC" in r[0] else None
            row = table.row()
            row.cell(r[0], style=st)
            row.cell(r[1], style=st)
            row.cell(r[2], style=st)

    pdf.ln(2.5)
    pdf.section_title("Avvertenze giuridiche")
    pdf.bullet("Le misure protettive", "nella CNC richiedono istanza e controllo giudiziale secondo gli artt. 18–19; non derivano automaticamente dalla sola intenzione di avviarla.")
    pdf.bullet("Il trattamento di tributi e contributi", "varia per strumento (artt. 23, 63 e 88 CCII); non si può presumere una falcidia. Il D.Lgs. 147/2026 ha esteso la disciplina pertinente anche ai tributi regionali e locali.")
    pdf.bullet("La newco", "è un possibile veicolo di continuità indiretta, non uno strumento per liberare la titolare dai debiti; vanno valutati art. 2560 c.c., rapporti di lavoro e disciplina delle cessioni concorsuali.")
    pdf.bullet("Liquidazione giudiziale:", "in un'eventuale liquidazione della persona fisica occorrerà esaminare presupposti ed effetti dell'esdebitazione (artt. 278 ss. CCII).")
    pdf.ln(1.5)

    pdf.body_p(
        "Normativa di riferimento: D.Lgs. 14/2019, testo vigente al 09/11/2026; D.Lgs. 147/2026 (GU 11/08/2026), artt. 2, 12, 18–19, 23, 57, 63, 74, 84, 121, 214, 278 ss. CCII; artt. 230-bis, 2560 e 2740 c.c. Inquadramento preliminare da validare con il legale.",
        line_height=3.2, size_pt=6.8, color=COLOR_TEXT_MUTED
    )

    # =========================================================================
    # PAGINA 7: 06 / CONCLUSIONI E PROPOSTA DI INCARICO
    # =========================================================================
    pdf.add_page()
    pdf.page_top_breadcrumb("06", "Conclusioni e Proposta di Incarico")

    # Banner Indirizzo preliminare
    ind_y = pdf.get_y()
    pdf.set_fill_color(*COLOR_CARD_BG)
    pdf.set_draw_color(*COLOR_BORDER)
    pdf.rect(15, ind_y, pdf.epw, 20, style="DF")
    pdf.set_xy(17, ind_y + 2)
    pdf.set_font(f_fam, "B", 8.5)
    pdf.set_text_color(*COLOR_NAVY)
    pdf.cell(pdf.epw - 4, 4.5, "PROPOSTA: VERIFICA DI FATTIBILITÀ DELLA COMPOSIZIONE NEGOZIATA", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(17, ind_y + 7.5)
    pdf.set_font(f_fam, "", 7.5)
    pdf.set_text_color(*COLOR_TEXT_DARK)
    pdf.multi_cell(pdf.epw - 4, 3.5, "Dare priorità a un incarico circoscritto volto a verificare se l'impresa, dopo la riorganizzazione, possa produrre cassa sufficiente a sostenere la gestione e un trattamento credibile delle passività. La CNC non è oggi assunta come procedura già scelta. In parallelo va mantenuto il confronto con liquidazione giudiziale e cessione in continuità indiretta.")

    pdf.set_y(ind_y + 23)
    pdf.section_title("Perché questa impostazione")
    pdf.bullet("L'impresa è operativa", "e conserva una base commerciale, ma il 2025 è in perdita e il pareggio del primo quadrimestre 2026 non è consolidato.")
    pdf.bullet("Il debito è elevato:", "€523.100,79 di esposizioni principali quantificate, considerando la coobbligazione personale, più €290–360 mila riferiti per fornitori, dipendenti e locazioni.")
    pdf.bullet("L'attivo concorsuale", "individuato è limitato e incompleto: senza crediti, magazzino e cespiti valorizzati non si può attestare la convenienza della continuità rispetto alla liquidazione.")
    pdf.ln(1.5)

    pdf.section_title("Verifiche essenziali dell'eventuale incarico successivo")
    col_w7 = (20, 90, 70)
    verif_rows = [
        ("1", "Consuntivo 2026 post-riduzione; margini per commessa e capacità produttiva", "EBITDA sostenibile"),
        ("2", "Scadenzari fornitori, dipendenti, locazioni, contratti finanziari e CTC aggiornata", "Debito riconciliato"),
        ("3", "Incassi, pagamenti, anticipi, saldi bancari, rimanenze, crediti e cespiti", "Cassa e attivo effettivo"),
        ("4", "Interlocuzione su crediti pubblici, disponibilità dei fornitori e ipotesi di cessione", "Confronto CNC / altre opzioni / liquidazione"),
    ]

    with pdf.table(
        col_widths=col_w7,
        headings_style=header_style,
        line_height=4.0,
        padding=(1.0, 1.5),
        borders_layout=TableBordersLayout.ALL,
        cell_fill_mode=TableCellFillMode.NONE,
        text_align=("CENTER", "LEFT", "LEFT"),
    ) as table:
        row = table.row()
        row.cell("Priorità")
        row.cell("Verifica mirata")
        row.cell("Risultato atteso")

        for r in verif_rows:
            row = table.row()
            row.cell(r[0], style=bold_style)
            row.cell(r[1])
            row.cell(r[2])

    pdf.ln(2.5)
    pdf.section_title("Conclusione")
    pdf.body_p(
        "Non è oggi possibile affermare che il risanamento sia fattibile. È però possibile proporre una verifica professionale mirata sulla CNC e sulle alternative, con un perimetro e risultati attesi definiti. Qualora la redditività normalizzata e la negoziabilità delle passività non trovassero riscontro, l'opzione liquidatoria dovrà essere valutata tempestivamente, considerando gli effetti personali sulla titolare.",
        line_height=3.8, size_pt=7.5
    )

    pdf.body_p(
        "Principali documenti utilizzati: Visura CCIAA 27/03/2026; Modelli Redditi PF 2024–2026; situazioni contabili 2024, 2025 e 30/04/2026; AdER «Da saldare», «Saldati», «Procedure attive» e moduli definizione agevolata; CR Banca d'Italia 29/10/2026 (ultimo dato agosto); visura CTC 29/10/2026; ricerca catastale, elenco beni, ispezione PRA; riepilogo dell'incontro 20/10/2026.",
        line_height=3.2, size_pt=6.5, color=COLOR_TEXT_MUTED
    )
    pdf.body_p(
        "Precisazione finale: la somma €523.100,79 combina date diverse e comprende €2.945 di rate residue riferite a una coobbligazione non scaduta. Le posizioni Findomestic e GIADA sono censite ma non maggiorate nel totale in assenza di evidenza di un debito ulteriore attuale. Il totale misto è soltanto indicativo e non sostituisce un elenco definitivo dei creditori.",
        line_height=3.2, size_pt=6.5, color=COLOR_TEXT_MUTED
    )

    return bytes(pdf.output())
