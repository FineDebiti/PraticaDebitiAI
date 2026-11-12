"""Suite di collaudo e regressione per il Benchmark D'Amico e il Motore di Audit (Sez. 6 Piano Tecnico).

Verifica i 6 criteri di accettazione obbligatori:
1. Ricostruzione debito Decimal: AdER €386.695,79 + CR €133.460 + Santander €2.945 = €523.100,79 (0 doppioni INPS/CR).
2. Scenari 2026: EBITDA base €1.202; con canone storico -€12.298 (~-€12,3k); riorganizzato €57.747-€67.747 (< rata €72k).
3. Inferenza fiscale RG5: blocco automatico RG5 -> incassi/cassa e verifica integrità testo su Pagina 2 PDF (nessun taglio di 'non').
4. Semantica Dati Assenti (NULL vs Zero): assenza Stato Patrimoniale -> PFN e PFN/EBITDA = None (mai €0,00 automatico).
5. Doppio elaborato sincronizzato: Relazione Cliente (7 pagine esatte) + Dossier Tecnico Audit (PDF valido con 13 anomalie e 6 obiezioni).
6. Quality Gate e Blocco Qualitativo: rilevazione anomalie rosse e attivazione obbligatoria Human Gate.
"""

from decimal import Decimal
import io
import pdfplumber

from app.services.forensic_audit_engine import (
    build_complete_technical_dossier,
    run_deterministic_decimal_audit,
    verify_inferences,
)
from app.services.benchmark_pdf_generator import generate_benchmark_7page_pdf
from app.services.technical_dossier_pdf_generator import generate_technical_dossier_pdf
from app.services.indicators import compute_indicators


def test_1_ricostruzione_debito_decimal_senza_duplicazioni():
    audit = run_deterministic_decimal_audit()
    totals = audit["totals_decimal"]

    assert Decimal(totals["ader_inps"]) + Decimal(totals["ader_altri"]) == Decimal("386695.79")
    assert Decimal(totals["ader_residuo"]) == Decimal("386695.79")
    assert Decimal(totals["cr_intesa"]) == Decimal("133460.00")
    assert Decimal(totals["ctc_santander"]) == Decimal("2945.00")
    assert Decimal(totals["banche_e_santander"]) == Decimal("136405.00")
    assert Decimal(totals["esposizioni_principali"]) == Decimal("523100.79")
    assert Decimal(totals["misto_min"]) == Decimal("813100.79")
    assert Decimal(totals["misto_max"]) == Decimal("883100.79")
    assert audit["all_quadrature_ok"] is True


def test_2_scenari_2026_e_confronto_rata():
    audit = run_deterministic_decimal_audit()
    totals = audit["totals_decimal"]

    assert Decimal(totals["ebitda_riorg_min"]) == Decimal("57747")
    assert Decimal(totals["ebitda_riorg_max"]) == Decimal("67747")
    # Anche il massimo dello scenario favorevole resta inferiore alla rata annua riferita di €72.000
    assert Decimal(totals["ebitda_riorg_max"]) < Decimal("72000")


def test_3_controllo_inferenza_fiscale_rg5_e_integrita_pdf_pagina_2():
    # 1. Verifica che il motore blocchi una frase assertiva errata ("€237 prova l'esistenza di margini")
    bad_check = verify_inferences("Il reddito fiscale dichiarato di €237 prova l'esistenza di margini o incassi ulteriori.")
    assert bad_check["all_passed"] is False

    # 2. Verifica che il testo corretto passi il gate
    good_check = verify_inferences(
        "Il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. "
        "Queste somme non sono incassi né fatturato."
    )
    assert good_check["all_passed"] is True

    # 3. Estrae il testo reale dalla Pagina 2 del PDF generato per verificare che "non prova" non sia tagliato sul margine destro
    pdf_bytes = generate_benchmark_7page_pdf({"header": {"cliente": "PIU' D'AMICO LUCREZIA", "data_bozza": "10.11.2026"}})
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) == 7
        page2_norm = " ".join((pdf.pages[1].extract_text() or "").split())
        assert "non prova l'esistenza di margini o incassi ulteriori" in page2_norm
        assert "Queste somme non sono incassi né fatturato" in page2_norm


def test_4_semantica_null_vs_zero_in_assenza_stato_patrimoniale():
    # Caso contabilità semplificata: presente solo Conto Economico, assente Stato Patrimoniale e debiti da bilancio
    ce_only = {
        "ricavi_vendite": {"corrente": 493094, "precedente": 783808},
        "valore_produzione": {"corrente": 493094, "precedente": 783808},
        "costi_produzione": {"corrente": 556637, "precedente": 647119},
        "differenza_valore_costi": {"corrente": -63543, "precedente": 136689},
        "ammortamenti": {"corrente": 20103, "precedente": 19898},
        "utile_perdita": {"corrente": -63605, "precedente": 127940},
    }
    inds = compute_indicators(sp={}, ce=ce_only, deb={})
    by_code = {i["code"]: i for i in inds}

    # PFN e PFN/EBITDA devono restare None (status 'na'), MAI 0.0 automatico!
    assert by_code["pfn"]["value_cur"] is None
    assert by_code["pfn"]["status"] == "na"
    assert by_code["pfn_ebitda"]["value_cur"] is None
    assert by_code["pfn_ebitda"]["status"] == "na"
    # L'EBITDA invece è regolarmente calcolato dal Conto Economico
    assert by_code["ebitda"]["value_cur"] == -43440.0


def test_5_coerenza_doppio_elaborato_e_dossier_tecnico_pdf():
    report_data = {"header": {"cliente": "PIU' D'AMICO LUCREZIA", "data_bozza": "10.11.2026"}, "_meta": {"version": 2}}
    dossier = build_complete_technical_dossier([], report_data)
    report_data["technical_dossier"] = dossier

    assert len(dossier["sources_matrix"]) == 10
    assert len(dossier["evidence_trace_map"]) == 13
    assert len(dossier["anomaly_register"]) == 13
    assert len(dossier["adversarial_review"]) == 6
    assert len(dossier["version_corrections"]) == 6

    dossier_pdf_bytes = generate_technical_dossier_pdf(report_data)
    assert dossier_pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(dossier_pdf_bytes)) as pdf:
        assert len(pdf.pages) >= 5
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        assert "523.100,79" in full_text
        assert "ANOM-01" in full_text
        assert "ANOM-13" in full_text
        assert "OBIEZ-01" in full_text
        assert "QUAD-03" in full_text


def test_6_blocco_qualitativo_e_human_gate():
    dossier = build_complete_technical_dossier([], {})
    qg = dossier["quality_gate"]
    assert qg["human_gate_required"] is True
    assert qg["counts"]["rosso"] == 3
    assert qg["counts"]["totale_anomalie"] == 13
    assert qg["gate_status"] == "VALIDATO_CON_RISERVA_ISTRUTTORIA"
