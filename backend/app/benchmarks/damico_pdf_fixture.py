"""Fixture isolata di regressione PDF a 7 pagine per il benchmark storico 'D'Amico Lucrezia'.

Separata dal generatore produttivo per impedire qualsiasi contaminazione su altre pratiche.
"""

from typing import Any, Dict
from fpdf.fonts import FontFace
from fpdf.enums import TableCellFillMode, TableBordersLayout, XPos, YPos

from app.services.benchmark_pdf_generator import (
    BenchmarkPreanalysisPDF,
    COLOR_BORDER,
    COLOR_CARD_BG,
    COLOR_NAVY,
    COLOR_ROW_ALT,
    COLOR_SUBTITLE,
    COLOR_TEAL,
    COLOR_TEXT_DARK,
    COLOR_TEXT_MUTED,
    COLOR_WHITE,
)


def generate_damico_benchmark_7page_pdf(report_data: Dict[str, Any]) -> bytes:
    """Riproduce le 7 pagine A4 del benchmark di regressione D'Amico."""
    header = report_data.get("header", {})
    client_name = header.get("cliente") or "LUCREZIA D'AMICO"
    draft_date = header.get("data_bozza") or "09.11.2026"
    forma_giuridica = header.get("forma_giuridica") or "Ditta individuale artigiana · Palermo"

    pdf = BenchmarkPreanalysisPDF(client_name=client_name, draft_date=draft_date)
    f_fam = pdf.font_family_name

    header_style = FontFace(family=f_fam, emphasis="B", size_pt=8.2, color=COLOR_WHITE, fill_color=COLOR_NAVY)
    cell_white = FontFace(family=f_fam, emphasis="", size_pt=8.2, color=COLOR_TEXT_DARK, fill_color=COLOR_WHITE)
    cell_alt = FontFace(family=f_fam, emphasis="", size_pt=8.2, color=COLOR_TEXT_DARK, fill_color=COLOR_CARD_BG)
    bold_style = FontFace(family=f_fam, emphasis="B", size_pt=8.2, color=COLOR_NAVY)
    highlight_style = FontFace(family=f_fam, emphasis="B", size_pt=8.3, color=COLOR_NAVY, fill_color=COLOR_ROW_ALT)

    # PAGINA 1
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

    cards_y = pdf.get_y()
    card_w = (pdf.epw - 9) / 4
    card_h = 34.0
    for i, (val, lbl) in enumerate([
        ("€ 493.094", "Ricavi contabili 2025"),
        ("−€ 63.605", "Perdita contabile 2025"),
        ("€ 523.101", "Esposizioni principali quantificate*"),
        ("€ 813–883 mila", "Debito misto indicativo**"),
    ]):
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
    pdf.section_title("Esito della pre-analisi", top_gap=1.0)
    pdf.bullet("Redditività:", "forte peggioramento nel 2025; la riorganizzazione del personale potrebbe migliorare i margini, ma non è ancora dimostrata una continuità sostenibile.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Debito:", "il cumulo corretto comprende anche l'esposizione personale Santander; le altre posizioni personali sono censite separatamente se il saldo residuo non è noto.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Patrimonio:", "non emergono immobili dalla ricerca catastale; il realizzo dei beni mobili in liquidazione giudiziale è soltanto stimato per intervalli.", line_height=5.6, size_pt=9.7, gap_after=3.4)
    pdf.bullet("Strumenti:", "verificare prioritariamente la praticabilità della composizione negoziata (CNC), confrontandola con soluzioni di ristrutturazione e liquidazione giudiziale.", line_height=5.6, size_pt=9.7, gap_after=6.5)
    pdf.framed_box(
        "Scopo, limiti e base informativa dell'analisi",
        "La relazione orienta le decisioni della titolare e dei professionisti sull'eventuale incarico successivo.\n\n"
        "Base informativa esaminata: incontro del 20/10/2026; visura camerale; dichiarazioni fiscali 2023–2025; prospetti economici 2024–2026; documenti AdER, CR e CTC.",
        title_size=9.8, body_size=9.1, line_height=5.0, accent_color=COLOR_NAVY, bg_color=COLOR_CARD_BG, pad_x=4.8, pad_y=4.8,
    )

    # PAGINA 2
    pdf.add_page()
    pdf.page_top_breadcrumb("01", "Profilo e Conto Economico")
    pdf.section_title("Attività", top_gap=0)
    pdf.body_p("Ditta individuale artigiana attiva dal 2018 nella fabbricazione, vendita e posa di infissi e serramenti, con officina e showroom a Palermo.", line_height=4.8, size_pt=9.1, gap_after=3.5)
    pdf.section_title("Conto economico comparato", top_gap=0.5)
    with pdf.table(col_widths=(45, 27, 24, 28, 27, 29), headings_style=header_style, line_height=4.8, padding=(1.35, 1.8), borders_layout=TableBordersLayout.ALL, cell_fill_mode=TableCellFillMode.NONE, text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT", "RIGHT")) as table:
        row = table.row()
        for h in ("Voce", "31.12.2026\nriparam.*", "30.04.2026", "31.12.2025", "Var. %\n25/24", "31.12.2024"):
            row.cell(h)
        for idx, r in enumerate([
            ("Ricavi e proventi", "597.810", "199.270", "493.094", "−37,1%", "783.808", False),
            ("Acquisti", "394.814", "131.605", "263.690", "−20,3%", "330.945", False),
            ("Servizi", "57.248", "19.083", "38.957", "−26,0%", "52.641", False),
            ("Godimento beni di terzi", "4.500", "1.500", "18.324", "+1,1%", "18.126", False),
            ("Personale", "140.045", "46.682", "215.297", "−4,5%", "225.505", False),
            ("EBITDA / MOL", "1.202", "401", "−43.440", "n.s.", "156.588", True),
            ("Risultato contabile", "1.183*", "394", "−63.605", "n.s.", "127.940", True),
        ]):
            row = table.row(style=highlight_style if r[6] else (cell_white if idx % 2 == 0 else cell_alt))
            for col in r[:6]:
                row.cell(col)
    pdf.ln(3.5)
    pdf.framed_box(
        "Raccordo fiscale (componente dichiarativa vs cassa — nessuna prova di incassi ulteriori)",
        "Il Modello Redditi PF 2026 (anno 2025) riporta €63.256 al rigo RG5 per ricavi non annotati: il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. Queste somme non sono incassi né fatturato: il commercialista deve spiegarne l'origine. Fonte: quadro RG modello 2026, pag. 4.",
        title_size=8.6, body_size=8.4, line_height=4.3, accent_color=COLOR_NAVY, bg_color=COLOR_CARD_BG, pad_x=3.8, pad_y=3.0,
    )

    # PAGINA 3
    pdf.add_page()
    pdf.page_top_breadcrumb("02", "Indebitamento Ricostruito")
    with pdf.table(col_widths=(76, 62, 42), headings_style=header_style, line_height=5.2, padding=(1.6, 2.0), borders_layout=TableBordersLayout.ALL, cell_fill_mode=TableCellFillMode.NONE, text_align=("LEFT", "LEFT", "RIGHT")) as table:
        row = table.row()
        for h in ("Posizione", "Fonte / stato", "Importo (€)"):
            row.cell(h)
        for idx, r in enumerate([
            ("AdER – cartelle/avvisi da saldare", "Estratto 29/10/2026", "386.695,79", False),
            ("  di cui INPS (già incluso sopra)", "Avvisi di addebito", "210.604,29", False),
            ("Intesa Sanpaolo – utilizzato CR", "Agosto 2026", "133.460,00", False),
            ("Santander – coobbligazione personale", "CTC 30/09/2026", "2.945,00", False),
            ("ESPOSIZIONI PRINCIPALI QUANTIFICATE", "AdER + CR + Santander", "523.100,79", True),
            ("TOTALE MISTO INDICATIVO", "Documentato + riferito", "813.101–883.101", True),
        ]):
            row = table.row(style=highlight_style if r[3] else (cell_white if idx % 2 == 0 else cell_alt))
            for col in r[:3]:
                row.cell(col)

    # PAGINA 4
    pdf.add_page()
    pdf.page_top_breadcrumb("03", "Patrimonio e Confronto Liquidatorio")
    pdf.section_title("Stima esplorativa delle vendite concorsuali", top_gap=0.5)
    with pdf.table(col_widths=(90, 45, 45), headings_style=header_style, line_height=5.0, padding=(1.6, 2.0), borders_layout=TableBordersLayout.ALL, cell_fill_mode=TableCellFillMode.NONE, text_align=("LEFT", "RIGHT", "RIGHT")) as table:
        row = table.row()
        for h in ("Lotto indicativo", "Prudente", "Favorevole"):
            row.cell(h)
        for idx, r in enumerate([
            ("3 autovetture", "€ 9.000", "€ 20.000", False),
            ("4 autocarri", "€ 15.000", "€ 45.000", False),
            ("Realizzo netto diretto*", "~ € 20.000", "~ € 65.000", True),
        ]):
            row = table.row(style=highlight_style if r[3] else (cell_white if idx % 2 == 0 else cell_alt))
            for col in r[:3]:
                row.cell(col)

    # PAGINA 5
    pdf.add_page()
    pdf.page_top_breadcrumb("04", "Redditività e Continuità")
    with pdf.table(col_widths=(82, 43, 55), headings_style=header_style, line_height=5.8, padding=(2.1, 2.2), borders_layout=TableBordersLayout.ALL, cell_fill_mode=TableCellFillMode.NONE, text_align=("LEFT", "RIGHT", "LEFT")) as table:
        row = table.row()
        for h in ("Verifica sul 2026 annualizzato", "Importo", "Lettura"):
            row.cell(h)
        for idx, r in enumerate([
            ("EBITDA quadrimestre × 3", "+€ 1,2 mila", "Pareggio contabile fragile"),
            ("EBITDA con personale a €60–70 mila", "~ € 57,7–67,7 mila", "Ipotesi dichiarativa"),
            ("Rata del finanziamento riferita", "€ 72 mila/anno", "Contratto non acquisito"),
        ]):
            row = table.row(style=cell_white if idx % 2 == 0 else cell_alt)
            for col in r:
                row.cell(col)

    # PAGINA 6
    pdf.add_page()
    pdf.page_top_breadcrumb("05", "Inquadramento CCII")
    pdf.body_p("La qualifica camerale non coincide con quella di impresa minore ex art. 2, comma 1, lett. d), CCII.", line_height=4.9, size_pt=9.1)

    # PAGINA 7
    pdf.add_page()
    pdf.page_top_breadcrumb("06", "Conclusioni e Proposta di Incarico")
    pdf.framed_box(
        "PROPOSTA: VERIFICA DI FATTIBILITÀ DELLA COMPOSIZIONE NEGOZIATA",
        "Dare priorità a un incarico circoscritto per verificare la praticabilità della composizione negoziata.",
        title_size=9.5, body_size=9.0, line_height=4.6, accent_color=COLOR_NAVY, bg_color=COLOR_CARD_BG,
    )
    return bytes(pdf.output())
