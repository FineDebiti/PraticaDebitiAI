"""Suite di collaudo e regressione per il Benchmark D'Amico, le 4 Criticità di Audit e
il 'Collaudo Decisivo DossierLex v2.1' (5 Prove Controllate su copie di test).

Verifica sia i 6 criteri base sia le 5 prove controllate richieste:
1. Alterazione del debito: modifica di un importo in una copia di test e verifica del ricalcolo automatico di quadrature, totali e scarti.
2. Dato assente: rimozione del saldo di un finanziamento e verifica che sia mostrato come sconosciuto (NULL), mai come zero (€0,00).
3. Errore RG5: testo che attribuisce ai ricavi non annotati RG5 (€63.256) un incasso effettivo -> bloccato automaticamente.
4. Fonte mancante: rimozione di un documento (es. DOC-04 AdER) -> segnalazione perdita di evidenza e revoca stato VERIFICATO.
5. Human Gate: tentativo di approvare il report senza prendere in carico tutte le anomalie rosse -> falsa approvazione bloccata.
"""

from decimal import Decimal
import io
import json
import pdfplumber

from app.benchmarks.damico_fixture import (
    build_damico_benchmark_technical_dossier as build_complete_technical_dossier,
    export_damico_benchmark_csv as export_audit_execution_csv,
    export_damico_benchmark_json as export_audit_execution_json,
    run_damico_controlled_verification_suite as run_controlled_verification_suite,
    run_damico_decimal_audit as run_deterministic_decimal_audit,
    verify_damico_inferences as verify_inferences,
)
from app.services.forensic_audit_engine import attempt_human_gate_approval
from app.benchmarks.damico_pdf_fixture import generate_damico_benchmark_7page_pdf as generate_benchmark_7page_pdf
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
    # Verifica quadratura CE 2025 al centesimo non arrotondato
    assert Decimal(totals["ricavi_2025_exact"]) - Decimal(totals["costi_operativi_2025_exact"]) == Decimal("-43439.87")
    assert Decimal(totals["perdita_2025_exact"]) == Decimal("-63605.00")
    assert audit["all_quadrature_ok"] is True


def test_2_scenari_2026_e_confronto_rata():
    audit = run_deterministic_decimal_audit()
    totals = audit["totals_decimal"]

    assert Decimal(totals["ebitda_riorg_min"]) == Decimal("57747.00")
    assert Decimal(totals["ebitda_riorg_max"]) == Decimal("67747.00")
    assert Decimal(totals["ebitda_riorg_max"]) < Decimal("72000.00")
    assert Decimal(totals["deficit_copertura_rata"]) == Decimal("-4253.00")


def test_3_controllo_inferenza_fiscale_rg5_e_integrita_pdf_pagina_2():
    bad_check = verify_inferences("Il reddito fiscale dichiarato di €237 prova l'esistenza di margini o incassi ulteriori.")
    assert bad_check["all_passed"] is False

    good_check = verify_inferences(
        "Il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori. "
        "Queste somme non sono incassi né fatturato."
    )
    assert good_check["all_passed"] is True

    pdf_bytes = generate_benchmark_7page_pdf({"header": {"cliente": "PIU' D'AMICO LUCREZIA", "data_bozza": "12.11.2026"}})
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) == 7
        page2_norm = " ".join((pdf.pages[1].extract_text() or "").split())
        assert "non prova l'esistenza di margini o incassi ulteriori" in page2_norm
        assert "Queste somme non sono incassi né fatturato" in page2_norm


def test_4_semantica_null_vs_zero_in_assenza_stato_patrimoniale():
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

    assert by_code["pfn"]["value_cur"] is None
    assert by_code["pfn"]["status"] == "na"
    assert by_code["pfn_ebitda"]["value_cur"] is None
    assert by_code["pfn_ebitda"]["status"] == "na"
    assert by_code["ebitda"]["value_cur"] == -43440.0


def test_5_sha256_completi_64_caratteri_e_coerenza_7_pagine_pdf():
    report_data = {"header": {"cliente": "PIU' D'AMICO LUCREZIA", "data_bozza": "12.11.2026"}, "_meta": {"version": 2}}
    dossier = build_complete_technical_dossier([], report_data)
    report_data["technical_dossier"] = dossier
    report_data["technical_dossier"]["collaudo_v21_suite"] = run_controlled_verification_suite()

    # Criticità B: Tutti i 10 gruppi documentali devono avere l'hash SHA-256 completo a 64 caratteri e l'elenco file
    for s in dossier["sources_matrix"]:
        assert len(s["sha256_full"]) == 64
        assert len(s["files_appartenenti"]) >= 1
        assert "copertura_pagine" in s
        assert "metodo_estrazione" in s

    # Criticità C & D: Nessuna auto-approvazione nel Quality Gate e corrispondenza esatta del numero di pagine
    qg = dossier["quality_gate"]
    assert qg["human_gate_approved"] is False
    assert qg["gate_status"] == "AUDIT_AUTOMATICO_SUPERATO__HUMAN_GATE_IN_ATTESA"
    qg06 = next(c for c in qg["checklist"] if c["test_id"] == "QG-06")
    assert "HUMAN GATE IN ATTESA" in qg06["esito"]
    assert "APPROVATO CON RISERVA" not in qg06["esito"]

    dossier_pdf_bytes = generate_technical_dossier_pdf(report_data)
    assert dossier_pdf_bytes.startswith(b"%PDF")
    with pdfplumber.open(io.BytesIO(dossier_pdf_bytes)) as pdf:
        assert len(pdf.pages) == dossier["expected_pages"] == 7
        p1_txt = pdf.pages[0].extract_text() or ""
        p2_txt = pdf.pages[1].extract_text() or ""
        p3_txt = pdf.pages[2].extract_text() or ""
        p4_txt = pdf.pages[3].extract_text() or ""
        p5_txt = pdf.pages[4].extract_text() or ""
        p6_txt = pdf.pages[5].extract_text() or ""
        p7_txt = pdf.pages[6].extract_text() or ""
        assert "SEZIONE 01" in p1_txt and "DOC-10" in p1_txt
        assert "SEZIONE 02" in p2_txt and "EV-13" in p2_txt
        assert "SEZIONE 03" in p3_txt and "QUAD-08" in p3_txt
        assert "SEZIONE 04" in p4_txt and "COLLAUDO-05" in p4_txt
        assert "SEZIONE 05" in p5_txt and "ANOM-13" in p5_txt
        assert "SEZIONE 06" in p6_txt and "OBIEZ-06" in p6_txt
        assert "SEZIONE 07" in p7_txt and "QG-06" in p7_txt
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
        assert "523.100,79" in full_text
        assert "HUMAN GATE IN ATTESA" in full_text
        assert "COLLAUDO-01" in full_text
        assert "COLLAUDO-05" in full_text


def test_6_export_json_e_csv_con_valori_sorgente_non_arrotondati():
    # Criticità A: verifica export JSON e CSV direttamente dal motore di calcolo
    json_str = export_audit_execution_json()
    parsed = json.loads(json_str)
    assert parsed["engine_version"] == "DossierLex-AuditEngine-v2.1-CCII"
    assert parsed["collaudo_v21_suite"]["all_5_passed"] is True
    quad05 = next(q for q in parsed["decimal_audit"]["quadrature"] if q["quad_id"] == "QUAD-05")
    assert quad05["valori_sorgente_non_arrotondati"]["ricavi_2025_exact"] == "493094.18"
    assert quad05["valori_sorgente_non_arrotondati"]["ebitda_2025_exact"] == "-43439.87"

    csv_str = export_audit_execution_csv()
    assert "QUAD-01" in csv_str
    assert "493094.18" in csv_str
    assert "523100.79" in csv_str


# ==============================================================================
# LE 5 PROVE CONTROLLATE DEL COLLAUDO DECISIVO DOSSIERLEX v2.1
# ==============================================================================
def test_collaudo_v21_1_alterazione_debito():
    """Prova 1: modificare un importo in una copia di test e verificare ricalcolo di totali, quadrature e scarti."""
    mutated = build_complete_technical_dossier(
        inputs_override={"cr_intesa": "150000.00", "atteso_esposizioni": "523100.79"}
    )
    totals = mutated["decimal_audit"]["totals_decimal"]
    assert Decimal(totals["banche_e_santander"]) == Decimal("152945.00")
    assert Decimal(totals["esposizioni_principali"]) == Decimal("539640.79")
    assert Decimal(totals["misto_min"]) == Decimal("829640.79")
    assert Decimal(totals["misto_max"]) == Decimal("899640.79")

    quad3 = next(q for q in mutated["decimal_audit"]["quadrature"] if q["quad_id"] == "QUAD-03")
    assert Decimal(quad3["scarto_raw"]) == Decimal("16540.00")
    assert "ERRORE QUADRATURA" in quad3["esito"]
    assert mutated["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"


def test_collaudo_v21_2_dato_assente_mai_zero():
    """Prova 2: eliminare il saldo di un finanziamento e verificare che venga mostrato come sconosciuto (NULL), mai zero."""
    mutated = build_complete_technical_dossier(inputs_override={"cr_intesa": None})
    totals = mutated["decimal_audit"]["totals_decimal"]
    assert totals["cr_intesa"] == "NULL"
    assert totals["banche_e_santander"] == "NULL"
    assert totals["esposizioni_principali"] == "NULL"

    quad2 = next(q for q in mutated["decimal_audit"]["quadrature"] if q["quad_id"] == "QUAD-02")
    assert quad2["valore_calcolato"] == "Non disponibile (NULL)"
    assert quad2["valore_calcolato"] != "€ 0,00"
    assert any(a["code"] == "ANOM-NULL-CR" for a in mutated["anomaly_register"])


def test_collaudo_v21_3_blocco_errore_rg5():
    """Prova 3: sottoporre al revisore un testo che attribuisce ai ricavi non annotati RG5 un incasso effettivo -> blocco."""
    testo_errato = (
        "L'iscrizione di € 63.256 al rigo RG5 come ricavi non annotati dimostra incassi effettivi "
        "non contabilizzati e una maggiore liquidità aziendale."
    )
    mutated = build_complete_technical_dossier(text_to_check=testo_errato)
    assert mutated["inference_audit"]["all_passed"] is False
    inf01 = mutated["inference_audit"]["checks"][0]
    assert inf01["esito"] == "BLOCCATO (ERRORE CRITICO)"
    assert mutated["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"


def test_collaudo_v21_4_fonte_mancante():
    """Prova 4: rimuovere un documento e controllare che il sistema segnali la perdita di evidenza e revochi VERIFICATO."""
    mutated = build_complete_technical_dossier(removed_source_ids=["DOC-04"])
    doc04 = next(s for s in mutated["sources_matrix"] if s["source_id"] == "DOC-04")
    assert doc04["file_attivo"] is False
    assert doc04["stato_verifica"] == "FONTE MANCANTE — DATO NON VERIFICATO"

    ev06 = next(e for e in mutated["evidence_trace_map"] if e["ev_id"] == "EV-06")
    ev09 = next(e for e in mutated["evidence_trace_map"] if e["ev_id"] == "EV-09")
    assert "NON VERIFICATO — FONTE MANCANTE (DOC-04)" in ev06["natura"]
    assert "NON VERIFICATO — FONTE MANCANTE (DOC-04)" in ev09["natura"]
    assert mutated["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"


def test_collaudo_v21_5_human_gate_blocco_falsa_approvazione():
    """Prova 5: tentare di approvare il report senza risolvere o prendere in carico le anomalie rosse -> bloccato."""
    dossier = build_complete_technical_dossier()

    # 1. Tentativo senza presa in carico integrale delle 3 anomalie rosse -> Respinto!
    res_blocked = attempt_human_gate_approval(
        dossier=dossier,
        professionista="Avv. Mario Rossi",
        anomalie_rosse_prese_in_carico=["ANOM-01"],  # Mancano ANOM-02 e ANOM-03
        note_istruttorie="Tentativo di approvazione parziale",
    )
    assert res_blocked["approved"] is False
    assert "BLOCCO HUMAN GATE" in res_blocked["stato_relazione"]
    assert "ANOM-02" in res_blocked["anomalie_rosse_non_gestite"]
    assert "ANOM-03" in res_blocked["anomalie_rosse_non_gestite"]

    # 2. Presa in carico esplicita e motivata di tutte le anomalie rosse -> Approvato!
    res_approved = attempt_human_gate_approval(
        dossier=dossier,
        professionista="Avv. Mario Rossi",
        anomalie_rosse_prese_in_carico=["ANOM-01", "ANOM-02", "ANOM-03"],
        note_istruttorie="Anomalie rosse prese in carico con mandato esplorativo condizionato a verifica documentale.",
    )
    assert res_approved["approved"] is True
    assert res_approved["stato_relazione"] == "RELAZIONE APPROVATA"
    assert res_approved["quality_gate"]["gate_status"] == "RELAZIONE_APPROVATA"
