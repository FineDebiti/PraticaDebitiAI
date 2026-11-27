"""Test deterministici Fase 3: Matrice giuridico-decisionale CCII in modalità simulazione e correzioni anomalie."""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    FinancialStatement,
    TaxDebtItem,
    TaxDebtStatement,
)
from app.services.case_indicators import compute_case_indicators
from app.services.indicators import compute_indicators
from app.services.protocols.ccii_matrix import (
    evaluate_ccii_matrix,
    load_ccii_catalog,
)
from app.services.protocols.classifier import ClassificationResult
from app.services.protocols.gate0 import Gate0Result
from app.services.statutory_knowledge import (
    calculate_test_pratico_ministeriale,
    check_ccii_segnali_allarme_art3,
    check_ccii_soglie_impresa_minore,
    classify_cinque_criticita,
    evaluate_pfn_ebitda,
)


def _cls(
    *,
    legal_form: str = "societa_capitali_srl",
    regime: str = "ordinaria",
    size: str = "non_minore",
    metrics: list[dict] | None = None,
    legal_evidence: list[str] | None = None,
) -> ClassificationResult:
    if metrics is None:
        if size == "non_minore":
            metrics = [
                {"year": 2023, "attivo": 450000.0, "ricavi": 320000.0, "supera_attivo_300k": True, "supera_ricavi_200k": True},
                {"year": 2024, "attivo": 420000.0, "ricavi": 290000.0, "supera_attivo_300k": True, "supera_ricavi_200k": True},
                {"year": 2025, "attivo": 390000.0, "ricavi": 260000.0, "supera_attivo_300k": True, "supera_ricavi_200k": True},
            ]
        elif size == "impresa_minore":
            metrics = [
                {"year": 2023, "attivo": 180000.0, "ricavi": 140000.0, "supera_attivo_300k": False, "supera_ricavi_200k": False},
                {"year": 2024, "attivo": 195000.0, "ricavi": 155000.0, "supera_attivo_300k": False, "supera_ricavi_200k": False},
                {"year": 2025, "attivo": 210000.0, "ricavi": 170000.0, "supera_attivo_300k": False, "supera_ricavi_200k": False},
            ]
        else:
            metrics = []
    return ClassificationResult(
        legal_form_profile=legal_form,
        legal_form_label=legal_form,
        legal_form_confidence="alto",
        legal_form_evidence=legal_evidence or [],
        accounting_regime=regime,
        accounting_regime_label=regime,
        ccii_size_qualification=size,
        ccii_size_label=size,
        ccii_metrics_by_year=metrics,
    )


def _gate0(
    *,
    level: str = "PREANALISI_SU_FASCICOLO_CONFERMATO",
    legal_form: str = "societa_capitali_srl",
    regime: str = "ordinaria",
    protocol: str | None = "B",
    missing_p0: list[dict] | None = None,
) -> Gate0Result:
    return Gate0Result(
        conclusivity_level=level,
        dossier_completeness_status="fascicolo_confermato" if level == "PREANALISI_SU_FASCICOLO_CONFERMATO" else "in_raccolta",
        effective_legal_form_profile=legal_form,
        effective_accounting_regime=regime,
        effective_protocol_code=protocol,
        source_inventory={},
        duplicate_groups=[],
        documenti_indispensabili_p0=missing_p0 or [],
    )


def _ledger(
    *,
    stato_dato: str = "VERIFICATO",
    cassa_certe: float | None = 620000.0,
    trib_entries: list[dict] | None = None,
    missing: list[str] | None = None,
    reconciliation_required: list[dict] | None = None,
) -> dict:
    return {
        "stato_dato": stato_dato,
        "riconciliazione_necessaria": bool(reconciliation_required),
        "reconciliation_required": reconciliation_required or [],
        "missing_sources_to_acquire": missing or [],
        "cr_temporal_status": "OMOGENEO" if stato_dato == "VERIFICATO" else "NON_VERIFICABILE_NULL",
        "cr_breakdown": {
            "cassa_effettiva": 220000.0 if cassa_certe is not None else None,
            "rischi_di_firma": 0.0,
            "garanzie_prestate": 0.0,
            "accordato_inutilizzato": 20000.0,
        },
        "buckets": {
            "tributari_contributivi": trib_entries if trib_entries is not None else [
                {
                    "source": "AdER",
                    "creditor": "Agenzia delle Entrate-Riscossione",
                    "description": "Cartella IRAP/IVA (erariale)",
                    "amount": 180000.0,
                    "exposure_kind": "cassa",
                    "status": "attivo",
                }
            ],
            "bancari_finanziari": [],
            "fornitori_dipendenti": [],
            "coobbligazioni_garanzie": [],
            "cessionari_factoring": [],
            "contestate_eventuali_non_quantificate": [],
            "estinte_e_piani_pagamento": [],
        },
        "totals": {
            "esposizioni_per_cassa_certe": cassa_certe,
        },
    }


def _formula(*, esma_compliant: bool = True, pfn_status: str = "VERIFICATO", ebitda_status: str = "VERIFICATO") -> dict:
    if esma_compliant:
        pfn_esma = {
            "code": "PFN_ESMA_CONFORME",
            "value": 340000.0,
            "validation_status": pfn_status,
            "inputs": {
                "componenti_esma": {"A_B_C_D": 360000.0, "cash": 20000.0},
                "esma_missing_components": [],
            },
        }
        pfn_fin = {
            "code": "PFN_GESTIONALE_SEMPLIFICATA",
            "value": 340000.0,
            "validation_status": "VERIFICATO",
            "inputs": {"esma_compliant": True},
        }
    else:
        pfn_esma = {
            "code": "PFN_ESMA_CONFORME",
            "value": None,
            "validation_status": "NON_VERIFICABILE_NULL",
            "inputs": {
                "esma_missing_components": ["debiti_leasing_breve", "debiti_commerciali_non_correnti"],
            },
        }
        pfn_fin = {
            "code": "PFN_GESTIONALE_SEMPLIFICATA",
            "value": 280000.0,
            "validation_status": "PARZIALE_CON_AVVISO",
            "inputs": {"esma_compliant": False},
        }
    return {
        "annual_periods": [
            {
                "period": "2025",
                "ebitda": {"code": "EBITDA_OIC12", "value": 85000.0, "validation_status": ebitda_status},
                "pfn_esma": pfn_esma,
                "pfn_finanziaria_gestionale": pfn_fin,
                "pfn_gestionale": {"code": "PFN_GESTIONALE_DEBT_LIKE", "value": 450000.0, "validation_status": "VERIFICATO" if esma_compliant else "PARZIALE_CON_AVVISO"},
            }
        ]
    }


def _fact(code: str, value: object, *, fdate: str = "2026-11-10", ddate: str = "2026-11-12", source: str = "Visura CCIAA / Documento", status: str = "VERIFICATO", confirmed: bool = False) -> dict:
    return {
        "fact_code": code,
        "value": value,
        "source": source,
        "fact_date": fdate,
        "document_date": ddate,
        "verification_status": status,
        "professional_confirmed": confirmed,
    }


def _by_code(res: dict) -> dict[str, dict]:
    return {s["rule_code"]: s for s in res["schede_valutazione"]}


def test_01_catalog_loads_14_rules_pending_and_dl168_suspended():
    catalog, sha = load_ccii_catalog()
    assert len(sha) == 64
    assert len(catalog.rules) == 14
    assert all(r.professional_approval_status == "PENDING_APPROVAL" for r in catalog.rules)
    assert all(r.active_in_production is False for r in catalog.rules)
    assert all(r.official_source_url.startswith("https://") for r in catalog.rules)
    assert any(s.rule_code == "CCII-SUSP-DL168-2026" and s.professional_approval_status == "SUSPENDED" for s in catalog.suspended_legislative_rules)


def test_02_parametric_catalog_reload_without_code_change(tmp_path):
    catalog, _ = load_ccii_catalog()
    raw = catalog.model_dump(mode="json")
    for r in raw["rules"]:
        if r["rule_code"] == "CCII-CPQ-01":
            r["parameters"]["ader_thresholds_eur"]["impresa_individuale"] = 125000.0
    custom_path = tmp_path / "custom_ccii.json"
    custom_path.write_text(json.dumps(raw), encoding="utf-8")

    res = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", regime="semplificata", size="non_minore"),
        _gate0(legal_form="impresa_individuale", regime="semplificata", protocol="A"),
        _ledger(),
        _formula(),
        assessment_date="2026-11-27",
        procedural_facts=[_fact("ader_scaduti_oltre_90gg", 110000.0, source="Estratto AdER")],
        catalog_path=custom_path,
    )
    cpq = _by_code(res)["CCII-CPQ-01"]
    assert "€ 125,000.00" in cpq["satisfied_requirements"][0]


def test_03_missing_or_invalid_assessment_date_raises():
    with pytest.raises(ValueError):
        evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="")
    with pytest.raises(ValueError):
        evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="27-11-2026")


def test_04_srl_sopra_soglia_completa_simulazione():
    facts = [
        _fact("stato_registro_imprese", "attiva", source="Visura CCIAA"),
        _fact("domanda_regolazione_debitore_pendente", False, source="Registro procedure"),
        _fact("rinuncia_domande_regolazione", False, source="Dichiarazione / visura"),
    ]
    res = evaluate_ccii_matrix(
        _cls(legal_form="societa_capitali_srl", regime="ordinaria", size="non_minore"),
        _gate0(level="PREANALISI_SU_FASCICOLO_CONFERMATO", legal_form="societa_capitali_srl", protocol="B"),
        _ledger(stato_dato="VERIFICATO", cassa_certe=620000.0),
        _formula(esma_compliant=True),
        assessment_date="2026-11-27",
        procedural_facts=facts,
        simulation_mode=True,
    )
    assert res["execution_mode"] == "SIMULAZIONE_NON_ATTIVA_IN_PRODUZIONE"
    assert res["automatic_recommendation"] is None
    assert res["human_gate_required"] is True
    assert res["catalog_approval_summary"]["any_rule_active_in_production"] is False
    cards = _by_code(res)
    assert cards["CCII-CNC-01"]["deterministic_outcome"] == "VERIFICATO"
    assert cards["CCII-CNC-01"]["active_in_production"] is False
    assert cards["CCII-PERI-CM"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert cards["CCII-PERI-CONS"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert cards["CCII-PERI-LC"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert cards["CCII-CS-01"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_05_srl_sotto_soglia_invarianza_protocollo_b():
    facts = [
        _fact("stato_registro_imprese", "attiva"),
        _fact("domanda_regolazione_debitore_pendente", False),
        _fact("rinuncia_domande_regolazione", False),
    ]
    res = evaluate_ccii_matrix(
        _cls(legal_form="societa_capitali_srl", regime="ordinaria", size="impresa_minore"),
        _gate0(legal_form="societa_capitali_srl", regime="ordinaria", protocol="B"),
        _ledger(stato_dato="VERIFICATO", cassa_certe=220000.0),
        _formula(esma_compliant=True),
        assessment_date="2026-11-27",
        procedural_facts=facts,
    )
    assert res["profile_snapshot"]["protocol_code"] == "B"
    cards = _by_code(res)
    assert cards["CCII-DIM-01"]["deterministic_outcome"] == "VERIFICATO"
    assert cards["CCII-CNC-02"]["deterministic_outcome"] == "VERIFICATO"
    assert cards["CCII-ADR-01"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert cards["CCII-PRO-CP"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_06_impresa_individuale_sopra_e_sotto_soglia():
    facts = [
        _fact("stato_registro_imprese", "attiva"),
        _fact("domanda_regolazione_debitore_pendente", False),
        _fact("rinuncia_domande_regolazione", False),
        _fact("ader_scaduti_oltre_90gg", 150000.0, source="Estratto AdER"),
    ]
    res_sopra = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", regime="semplificata", size="non_minore"),
        _gate0(legal_form="impresa_individuale", regime="semplificata", protocol="A"),
        _ledger(stato_dato="VERIFICATO", cassa_certe=650000.0),
        _formula(esma_compliant=False),
        assessment_date="2026-11-27",
        procedural_facts=facts,
    )
    cards_s = _by_code(res_sopra)
    assert res_sopra["profile_snapshot"]["protocol_code"] == "A"
    assert "€ 100,000.00" in cards_s["CCII-CPQ-01"]["satisfied_requirements"][0]
    assert "AdER scaduto >90gg verificato" in " ".join(cards_s["CCII-CPQ-01"]["satisfied_requirements"])
    assert cards_s["CCII-PERI-CM"]["deterministic_outcome"] == "NON_SODDISFATTO"

    res_sotto = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", regime="semplificata", size="impresa_minore"),
        _gate0(legal_form="impresa_individuale", regime="semplificata", protocol="A"),
        _ledger(stato_dato="VERIFICATO", cassa_certe=180000.0),
        _formula(esma_compliant=False),
        assessment_date="2026-11-27",
        procedural_facts=facts,
    )
    assert _by_code(res_sotto)["CCII-CNC-02"]["deterministic_outcome"] == "VERIFICATO"


def test_07_gate0_exact_states_and_invalid_state_rejected():
    res_delim = evaluate_ccii_matrix(
        _cls(),
        _gate0(level="DIAGNOSI_PRELIMINARE_DELIMITATA"),
        _ledger(),
        _formula(),
        assessment_date="2026-11-27",
    )
    assert res_delim["profile_snapshot"]["gate0"]["valid_state"] is True
    assert res_delim["profile_snapshot"]["gate0"]["dossier_confirmed"] is False

    res_bad = evaluate_ccii_matrix(
        _cls(),
        _gate0(level="DIAGNOSI_COMPLETA"),
        _ledger(),
        _formula(),
        assessment_date="2026-11-27",
    )
    assert res_bad["profile_snapshot"]["gate0"]["valid_state"] is False
    assert res_bad["profile_snapshot"]["gate0"]["dossier_confirmed"] is False
    assert "ANOMALIA" in (res_bad["profile_snapshot"]["gate0"]["anomaly"] or "").upper() or "non riconosciuto" in (res_bad["profile_snapshot"]["gate0"]["anomaly"] or "").lower()


def test_08_pfn_esma_exact_contract_and_wrong_status_guard():
    res_ok = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(esma_compliant=True, pfn_status="VERIFICATO"),
        assessment_date="2026-11-27",
    )
    assert res_ok["profile_snapshot"]["pfn_esma"]["esma_compliant"] is True
    assert res_ok["profile_snapshot"]["pfn_esma"]["pfn_esma_value"] == 340000.0

    # Stato inventato PFN_ESMA_CONFORME in validation_status NON deve passare come ESMA conforme
    res_wrong_status = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(esma_compliant=True, pfn_status="PFN_ESMA_CONFORME"),
        assessment_date="2026-11-27",
    )
    assert res_wrong_status["profile_snapshot"]["pfn_esma"]["esma_compliant"] is False

    res_incomp = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(esma_compliant=False),
        assessment_date="2026-11-27",
    )
    assert res_incomp["profile_snapshot"]["pfn_esma"]["esma_compliant"] is False
    assert res_incomp["profile_snapshot"]["pfn_esma"]["pfn_esma_value"] is None


def test_09_misure_protettive_non_automatiche_art18_19():
    res_none = evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="2026-11-27")
    assert _by_code(res_none)["CCII-CNC-MP"]["deterministic_outcome"] == "NON_DETERMINABILE"

    # Ricorso tardivo (2 giorni dopo pubblicazione R.I.) -> NON_SODDISFATTO
    res_late = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-10-15",
        procedural_facts=[
            _fact("pubblicazione_ri_misure_protettive", True, fdate="2026-10-01", ddate="2026-10-01"),
            _fact("ricorso_tribunale_misure_protettive", True, fdate="2026-10-03", ddate="2026-10-03"),
        ],
    )
    assert _by_code(res_late)["CCII-CNC-MP"]["deterministic_outcome"] == "NON_SODDISFATTO"

    # Ricorso giorno successivo + ordinanza entro 240gg -> VERIFICATO; oltre 240gg -> NON_SODDISFATTO
    facts_ok = [
        _fact("pubblicazione_ri_misure_protettive", True, fdate="2026-01-10", ddate="2026-01-10"),
        _fact("ricorso_tribunale_misure_protettive", True, fdate="2026-01-11", ddate="2026-01-11"),
        _fact("ordinanza_tribunale_misure_protettive", True, fdate="2026-02-01", ddate="2026-02-01"),
    ]
    res_valid = evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="2026-05-01", procedural_facts=facts_ok)
    assert _by_code(res_valid)["CCII-CNC-MP"]["deterministic_outcome"] == "VERIFICATO"
    res_exp = evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="2026-10-01", procedural_facts=facts_ok)
    assert _by_code(res_exp)["CCII-CNC-MP"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_10_misure_premiali_solo_ade_non_a_ruolo_art25bis():
    # Tutti a ruolo -> NON_SODDISFATTO
    res_ruolo = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-11-27",
        procedural_facts=[_fact("esito_idoneo_cnc_art25bis", True)],
    )
    assert _by_code(res_ruolo)["CCII-CNC-PREM"]["deterministic_outcome"] == "NON_SODDISFATTO"

    # Tributi non ancora iscritti a ruolo -> VERIFICATO (concede AdE, non esperto)
    res_non_ruolo = evaluate_ccii_matrix(
        _cls(), _gate0(),
        _ledger(trib_entries=[{
            "source": "Dichiarazione / Cassetto fiscale",
            "creditor": "Agenzia delle Entrate",
            "description": "IVA non ancora iscritta a ruolo",
            "amount": 45000.0,
            "exposure_kind": "cassa",
            "status": "attivo",
        }]),
        _formula(),
        assessment_date="2026-11-27",
        procedural_facts=[_fact("esito_idoneo_cnc_art25bis", True)],
    )
    prem = _by_code(res_non_ruolo)["CCII-CNC-PREM"]
    assert prem["deterministic_outcome"] == "VERIFICATO"
    assert "Agenzia delle Entrate" in " ".join(prem["satisfied_requirements"])


def test_11_concordato_semplificato_art25sexies_60_giorni():
    facts_rel = [
        _fact("relazione_finale_esperto_cnc", True, fdate="2026-09-28", ddate="2026-09-28", source="Relazione finale CNC"),
        _fact("attestazione_correttezza_buona_fede_esperto", True, fdate="2026-09-28", ddate="2026-09-28", source="Relazione finale CNC"),
        _fact("attestazione_impraticabilita_art23", True, fdate="2026-09-28", ddate="2026-09-28", source="Relazione finale CNC"),
    ]
    # 2026-11-27 è esattamente +60 giorni da 2026-09-28
    res_day60 = evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="2026-11-27", procedural_facts=facts_rel)
    assert _by_code(res_day60)["CCII-CS-01"]["procedural_requirement_status"] == "VERIFICATO"

    # 2026-11-28 è giorno 61 -> decaduto NON_SODDISFATTO
    res_day61 = evaluate_ccii_matrix(_cls(), _gate0(), _ledger(), _formula(), assessment_date="2026-11-28", procedural_facts=facts_rel)
    assert _by_code(res_day61)["CCII-CS-01"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_12_art23_co2bis_esclude_inps_e_applica_dlgs147_2026_con_assessment_date():
    trib_misto = [
        {"source": "Comune di Palermo", "creditor": "Comune di Palermo", "description": "IMU e TARI scadute", "amount": 32000.0, "exposure_kind": "cassa", "status": "attivo"},
        {"source": "INPS", "creditor": "INPS", "description": "Contributi previdenziali INPS", "amount": 50000.0, "exposure_kind": "cassa", "status": "attivo"},
    ]
    facts_rel = [
        _fact("relazione_convenienza_art23_co2bis", True, source="Relazione indipendente"),
        _fact("relazione_veridicita_revisore_art23_co2bis", True, source="Relazione revisore legale"),
        _fact("cnc_attiva_o_avviata", True, fdate="2026-07-01", ddate="2026-07-01", source="Istanza CCIAA"),
    ]
    # Ante 12/08/2026: solo IMU/TARI + INPS -> entrambi fuori art. 23 co. 2-bis -> NON_SODDISFATTO
    res_pre = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(trib_entries=trib_misto), _formula(),
        assessment_date="2026-08-11",
        procedural_facts=facts_rel,
    )
    assert _by_code(res_pre)["CCII-CNC-TF"]["deterministic_outcome"] == "NON_SODDISFATTO"

    # Dal 12/08/2026: IMU/TARI incluse ex Art. 4 D.Lgs. 147/2026, INPS ancora escluso, warning transitorio per CNC del 2026-07-01
    res_post = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(trib_entries=trib_misto), _formula(),
        assessment_date="2026-08-12",
        procedural_facts=facts_rel,
    )
    tf = _by_code(res_post)["CCII-CNC-TF"]
    assert tf["deterministic_outcome"] == "VERIFICATO"
    assert any("INPS/INAIL" in s and "ESCLUSI" in s for s in tf["satisfied_requirements"])
    assert any("2026-07-01" in t for t in tf["exceptions_and_transitional"])


def test_13_art25quinquies_rinuncia_4_mesi_e_lg_terzi():
    # Rinuncia del 2026-08-01 -> alla assessment_date 2026-11-27 (entro 4 mesi -> 2026-12-01) preclusa
    res_blocked = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-11-27",
        procedural_facts=[
            _fact("stato_registro_imprese", "attiva"),
            _fact("domanda_regolazione_debitore_pendente", False),
            _fact("rinuncia_domande_regolazione", True, fdate="2026-08-01", ddate="2026-08-01"),
        ],
    )
    assert _by_code(res_blocked)["CCII-CNC-01"]["deterministic_outcome"] == "NON_SODDISFATTO"

    # Oltre i 4 mesi (2026-12-02) + istanza LG di terzi pendente -> NON preclusa
    res_open = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-12-02",
        procedural_facts=[
            _fact("stato_registro_imprese", "attiva"),
            _fact("domanda_regolazione_debitore_pendente", False),
            _fact("rinuncia_domande_regolazione", True, fdate="2026-08-01", ddate="2026-08-01"),
            _fact("istanza_lg_terzi_pendente", True, fdate="2026-11-20", ddate="2026-11-20"),
        ],
    )
    cnc = _by_code(res_open)["CCII-CNC-01"]
    assert cnc["deterministic_outcome"] == "VERIFICATO"
    assert any("terzi" in s.lower() for s in cnc["satisfied_requirements"])


def test_14_soglie_art25novies_differenziate_e_5_dimensioni_no_auto_rec():
    # €150.000 AdER >90gg: supera per ditta individuale (100k), NON supera per s.n.c. (200k) né s.r.l. (500k)
    facts_cpq = [
        _fact("ader_scaduti_oltre_90gg", 150000.0),
        _fact("inps_scaduti_oltre_90gg", 0.0),
        _fact("inps_ha_dipendenti", False),
        _fact("inail_premi_scaduti_oltre_90gg", 0.0),
        _fact("ade_iva_lipe_scaduta", 0.0),
    ]
    r_ind = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", size="non_minore"),
        _gate0(legal_form="impresa_individuale", protocol="A"),
        _ledger(), _formula(), assessment_date="2026-11-27", procedural_facts=facts_cpq,
    )
    r_snc = evaluate_ccii_matrix(
        _cls(legal_form="societa_persone", size="non_minore"),
        _gate0(legal_form="societa_persone", protocol=None),
        _ledger(), _formula(), assessment_date="2026-11-27", procedural_facts=facts_cpq,
    )
    assert _by_code(r_ind)["CCII-CPQ-01"]["deterministic_outcome"] == "VERIFICATO"
    assert _by_code(r_snc)["CCII-CPQ-01"]["deterministic_outcome"] == "NON_SODDISFATTO"
    for card in r_snc["schede_valutazione"]:
        assert card["professional_evaluation_required"] is True
        assert card["reserved_to_professional"]
        assert "NON costituisce ammissione certa" in card["outcome_disclaimer"]


def test_15_categorie_non_supportate_e_agricola_startup_no_ateco():
    # Consumatore mai assimilato a Protocolli A/B
    r_cons = evaluate_ccii_matrix(
        _cls(legal_form="persona_fisica_non_imprenditore", regime="non_documentato", size="non_applicabile"),
        _gate0(legal_form="persona_fisica_non_imprenditore", regime="non_documentato", protocol=None),
        _ledger(cassa_certe=80000.0), _formula(esma_compliant=False),
        assessment_date="2026-11-27",
    )
    assert r_cons["profile_snapshot"]["protocol_code"] is None
    assert _by_code(r_cons)["CCII-PERI-CONS"]["subjective_requirement_status"] == "VERIFICATO"
    assert _by_code(r_cons)["CCII-CNC-01"]["deterministic_outcome"] == "NON_SODDISFATTO"

    # Solo indizio ATECO "01.11" / "startup innovativa" -> NON certifica impresa agricola né startup innovativa
    r_hint = evaluate_ccii_matrix(
        _cls(legal_form="societa_capitali_srl", size="impresa_minore", legal_evidence=["ATECO 01.11 coltivazione", "startup innovativa"]),
        _gate0(), _ledger(cassa_certe=150000.0), _formula(),
        assessment_date="2026-11-27",
    )
    assert r_hint["profile_snapshot"]["special_categories"]["impresa_agricola"]["certified"] is False
    assert r_hint["profile_snapshot"]["special_categories"]["impresa_agricola"]["status"] == "INDIZIO_NON_CONFERMATO"
    assert r_hint["profile_snapshot"]["special_categories"]["startup_innovativa"]["status"] == "INDIZIO_NON_CONFERMATO"
    assert _by_code(r_hint)["CCII-ADR-01"]["deterministic_outcome"] == "NON_DETERMINABILE"


def test_16_art33_co4_cancellazione_e_art268_debitore_vs_creditore():
    # Imprenditore cancellato R.I. -> Concordato Minore NON_SODDISFATTO ex art. 33 co. 4, ma LC istanza debitore ammessa nel perimetro (art. 33 co. 1-bis)
    facts_canc = [
        _fact("stato_registro_imprese", "cancellata", fdate="2026-02-01", ddate="2026-02-10"),
        _fact("soggetto_istante_liquidazione_controllata", "debitore"),
    ]
    res_canc = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", size="impresa_minore"),
        _gate0(legal_form="impresa_individuale", protocol="A"),
        _ledger(cassa_certe=35000.0), _formula(esma_compliant=False),
        assessment_date="2026-11-27", procedural_facts=facts_canc,
    )
    cards = _by_code(res_canc)
    assert cards["CCII-PERI-CM"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert "33" in " ".join(cards["CCII-PERI-CM"]["blocking_conditions_verified"])
    assert cards["CCII-PERI-LC"]["objective_requirement_status"] == "VERIFICATO"

    # Su istanza del creditore con debiti scaduti < €50.000 -> CCII-PERI-LC = NON_SODDISFATTO ex art. 268 co. 2
    res_cred = evaluate_ccii_matrix(
        _cls(legal_form="impresa_individuale", size="impresa_minore"),
        _gate0(legal_form="impresa_individuale", protocol="A"),
        _ledger(cassa_certe=40000.0), _formula(esma_compliant=False),
        assessment_date="2026-11-27",
        procedural_facts=[
            _fact("soggetto_istante_liquidazione_controllata", "creditore"),
            _fact("debiti_scaduti_non_pagati_art268_co2", 40000.0, source="Estratti AdER/CR"),
        ],
    )
    assert _by_code(res_cred)["CCII-PERI-LC"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_17_debt_ledger_riconciliazione_e_null_bloccano_certificazione():
    res_rec = evaluate_ccii_matrix(
        _cls(legal_form="societa_capitali_srl", size="non_determinabile"),
        _gate0(level="DIAGNOSI_PRELIMINARE_DELIMITATA"),
        _ledger(
            stato_dato="RICONCILIAZIONE_NECESSARIA",
            cassa_certe=310000.0,
            reconciliation_required=[{"code": "RICONCILIAZIONE_BANCA_CR_1", "message": "Scostamento CR"}],
        ),
        _formula(esma_compliant=False),
        assessment_date="2026-11-27",
    )
    assert res_rec["profile_snapshot"]["debt_mass_verified"] is False
    cards = _by_code(res_rec)
    assert cards["CCII-DIM-01"]["deterministic_outcome"] == "NON_DETERMINABILE"
    assert cards["CCII-CNC-TF"]["deterministic_outcome"] == "NON_DETERMINABILE"
    assert cards["CCII-ADR-01"]["deterministic_outcome"] == "NON_DETERMINABILE"


def test_18_procedural_facts_incompleti_o_non_verificati_rifiutati():
    res = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-11-27",
        procedural_facts=[
            {"fact_code": "stato_registro_imprese", "value": "attiva"},  # manca source e date!
            _fact("domanda_regolazione_debitore_pendente", False, status="NON_VERIFICATO", confirmed=False),
        ],
    )
    assert len(res["rejected_or_unverified_procedural_facts"]) == 2
    assert _by_code(res)["CCII-CNC-01"]["deterministic_outcome"] == "NON_DETERMINABILE"


def test_19_simulation_mode_false_blocca_tutte_le_regole_pending_approval():
    res = evaluate_ccii_matrix(
        _cls(), _gate0(), _ledger(), _formula(),
        assessment_date="2026-11-27",
        simulation_mode=False,
    )
    for card in res["schede_valutazione"]:
        assert card["execution_status"] == "BLOCCATA_IN_ATTESA_APPROVAZIONE"
        assert card["deterministic_outcome"] == "NON_DETERMINABILE"
        assert card["active_in_production"] is False


def test_20_anomalie_preesistenti_corrette(db_session):
    # 1. check_ccii_soglie_impresa_minore su NULL -> nessuna procedura sopra soglia in fallback; S.r.l. niente art. 283
    null_res = check_ccii_soglie_impresa_minore([], [], None, legal_form_profile="societa_capitali_srl")
    assert null_res["procedure_esperibili"] == []

    srl_min = check_ccii_soglie_impresa_minore([100000.0], [100000.0], 200000.0, legal_form_profile="societa_capitali_srl", debt_mass_verified=True)
    assert all("283" not in p for p in srl_min["procedure_esperibili"])
    assert any("25-quater" in p for p in srl_min["procedure_esperibili"])

    # 2. check_ccii_segnali_allarme_art3: None non diventa 'nessun segnale' e ditta individuale usa €100k
    art3_partial = check_ccii_segnali_allarme_art3(
        None, None, None, None, None, None, None, 150000.0, tipo_soggetto="impresa_individuale",
    )
    assert art3_partial["soglia_ader_applicata"] == 100000.0
    assert art3_partial["ha_segnali_allarme_art3"] is True
    assert art3_partial["valutazione_per_lettera"]["a_retribuzioni"] == "NON_DETERMINABILE"

    art3_none = check_ccii_segnali_allarme_art3(
        None, None, None, None, None, None, None, 20000.0, tipo_soggetto="impresa_individuale",
    )
    assert art3_none["ha_segnali_allarme_art3"] is False
    assert "NON_DETERMINABILE" in art3_none["obbligo_adeguati_assetti"]

    # 3. Nessun automatismo giuridico in calculate_test_pratico_ministeriale, evaluate_pfn_ebitda, classify_cinque_criticita
    tp = calculate_test_pratico_ministeriale(400000.0, flusso_annuo_servizio_debito=100000.0)
    assert "art. 63" not in tp["descrizione_esito"].lower()
    pfn_eb = evaluate_pfn_ebitda(1500000.0, 100000.0)
    assert "presupposto oggettivo" not in pfn_eb["valutazione_bancaria"].lower()
    crit = classify_cinque_criticita(60000.0, 50000.0, 40000.0, 10000.0, 100000.0, "warn", True, False, False)
    assert "supera le soglie di allarme" not in crit[0]["descrizione"].lower()

    # 4. indicators.py non chiama ESMA conforme un dataset incompleto
    inds = compute_indicators(sp={"disponibilita_liquide": {"corrente": 10000.0}}, ce={}, deb={"banche": {"importo": 50000.0}})
    pfn_ind = next(i for i in inds if i["code"] == "pfn")
    assert "non pienamente esma" in pfn_ind["label"].lower()

    # 5. case_indicators.py applica €100k a ditta individuale (non €200k!)
    case = Case(client_name="Ditta Test", status="ready")
    db_session.add(case)
    db_session.flush()
    db_session.add(Company(case_id=case.id, role="cliente", name="Ditta Test", company_type="individuale", legal_form="Impresa individuale"))
    stmt = TaxDebtStatement(case_id=case.id, total_residuo=150000.0, total_residuo_netto=150000.0)
    db_session.add(stmt)
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=stmt.id, ente_categoria="erariale", totale_residuo=150000.0, totale_residuo_netto=150000.0))
    db_session.commit()

    ci = compute_case_indicators(db_session, case.id)
    art3_ci = next(i for i in ci["indicators"] if i["code"] == "ccii_segnali_art3")
    assert art3_ci["status"] == "danger"
    assert "Presenti" in str(art3_ci["value"])


def test_21_api_ccii_matrix_simulation_readonly_endpoint(db_session):
    case = Case(client_name="Alfa S.r.l.", status="ready")
    db_session.add(case)
    db_session.flush()
    comp = Company(case_id=case.id, role="cliente", name="Alfa S.r.l.", legal_form="S.r.l.")
    db_session.add(comp)
    db_session.flush()
    db_session.add(FinancialStatement(
        company_id=comp.id,
        fiscal_year_end="2025-12-31",
        statement_type="bilancio_annuale",
        revenues=350000.0,
        total_assets=410000.0,
        total_debts=600000.0,
        equity=80000.0,
    ))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Alfa", category="rischi_autoliquidanti", reference_month="2026-09", accordato=100000.0, utilizzato=80000.0))
    db_session.commit()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app)
        r_bad = client.get(f"/api/cases/{case.id}/ccii-matrix-simulation", params={"assessment_date": "invalid"})
        assert r_bad.status_code == 422

        r_ok = client.get(f"/api/cases/{case.id}/ccii-matrix-simulation", params={"assessment_date": "2026-11-27"})
        assert r_ok.status_code == 200
        body = r_ok.json()
        assert body["case_id"] == case.id
        m = body["ccii_matrix"]
        assert m["simulation_mode"] is True
        assert m["automatic_recommendation"] is None
        assert m["assessment_date"] == "2026-11-27"
        assert len(m["schede_valutazione"]) == 14
        assert all(c["active_in_production"] is False for c in m["schede_valutazione"])
    finally:
        app.dependency_overrides.clear()
