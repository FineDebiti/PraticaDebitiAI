"""Test per il modulo di Conoscenza Integrata Giuridico-Contabile (statutory_knowledge)."""
import pytest
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    check_ccii_soglie_impresa_minore,
    check_ccii_segnali_allarme_art3,
)


def test_calculate_ebitda_oic12_standard():
    ce = {
        "valore_produzione": 500000.0,
        "ricavi_vendite": 480000.0,
        "costi_produzione": 440000.0,
        "differenza_valore_costi": 60000.0,  # A - B = 60,000
        "ammortamento_immateriali": 10000.0, # B10a
        "ammortamento_materiali": 25000.0,   # B10b
        "svalutazioni_immobilizzazioni": 5000.0, # B10c
        "svalutazione_crediti": 8000.0,      # B10d (non va aggiunto a EBITDA)
    }
    res = calculate_ebitda_oic12(ce)
    # EBITDA standard = 60000 + 10000 + 25000 + 5000 = 100000
    assert res["ebit_differenza_a_b"] == 60000.0
    assert res["ammortamenti_b10a_b10b_b10c"] == 40000.0
    assert res["ebitda_standard"] == 100000.0
    assert res["ebitda_margin_pct"] == 20.0


def test_calculate_ebitda_oic12_with_leasing():
    ce = {
        "valore_produzione": 300000.0,
        "costi_produzione": 270000.0,
        "differenza_valore_costi": 30000.0,
        "ammortamenti": 15000.0,
    }
    # Canoni leasing B8 = 10,000 per EBITDA rettificato
    res = calculate_ebitda_oic12(ce, leasing_b8=10000.0)
    assert res["ebitda_standard"] == 45000.0
    assert res["ebitda_rettificato"] == 55000.0


def test_calculate_pfn_esma():
    res = calculate_pfn_esma(
        debiti_bancari_breve=50000.0,
        debiti_bancari_medio_lungo=150000.0,
        disponibilita_liquide=20000.0,
        tfr_fondo=30000.0,
        finanziamenti_soci=10000.0,
        debiti_tributari_scaduti=40000.0,
        debiti_fornitori_scaduti_90gg=15000.0,
    )
    # Debiti fin: 50k + 150k = 200k
    # Debt-like: 30k + 10k + 40k + 15k = 95k
    # Totale passività: 295k
    # Cassa: 20k
    # PFN: 295k - 20k = 275k
    assert res["debiti_finanziari_breve"] == 50000.0
    assert res["debiti_finanziari_medio_lungo"] == 150000.0
    assert res["debt_like_items"]["totale_debt_like"] == 95000.0
    assert res["pfn_totale"] == 275000.0


def test_evaluate_pfn_ebitda_thresholds():
    # 1. Cassa netta (PFN <= 0)
    e1 = evaluate_pfn_ebitda(-10000.0, 50000.0)
    assert e1["status"] == "ok"
    assert e1["classe_merito"] == "cassa_netta"

    # 2. EBITDA negativo con debito
    e2 = evaluate_pfn_ebitda(100000.0, -5000.0)
    assert e2["status"] == "danger"
    assert e2["classe_merito"] == "squilibrio_grave"

    # 3. Solida (< 2.0)
    e3 = evaluate_pfn_ebitda(150000.0, 100000.0) # 1.5
    assert e3["status"] == "ok"
    assert e3["classe_merito"] == "solida"

    # 4. Fisiologica (2.0 - 3.0)
    e4 = evaluate_pfn_ebitda(250000.0, 100000.0) # 2.5
    assert e4["status"] == "ok"
    assert e4["classe_merito"] == "fisiologica"

    # 5. Attenzione (3.0 - 6.0)
    e5 = evaluate_pfn_ebitda(450000.0, 100000.0) # 4.5
    assert e5["status"] == "warn"
    assert e5["classe_merito"] == "attenzione"

    # 6. Allarme bancario / UTP (6.0 - 12.0)
    e6 = evaluate_pfn_ebitda(800000.0, 100000.0) # 8.0
    assert e6["status"] == "danger"
    assert e6["classe_merito"] == "allarme_bancario"

    # 7. Sofferenza (> 12.0)
    e7 = evaluate_pfn_ebitda(1500000.0, 100000.0) # 15.0
    assert e7["status"] == "danger"
    assert e7["classe_merito"] == "sofferenza"


def test_ccii_impresa_minore():
    # Entro le soglie (Attivo <= 300k, Ricavi <= 200k, Debiti <= 500k)
    res_minore = check_ccii_soglie_impresa_minore(
        attivo_patrimoniale_triennio=[250000.0, 280000.0],
        ricavi_lordi_triennio=[150000.0, 180000.0],
        debiti_totali_attuali=400000.0,
    )
    assert res_minore["e_impresa_minore"] is True
    assert "Concordato Minore" in res_minore["procedure_esperibili"][0]

    # Sopra soglia (Debiti > 500k)
    res_sopra = check_ccii_soglie_impresa_minore(
        attivo_patrimoniale_triennio=[250000.0],
        ricavi_lordi_triennio=[180000.0],
        debiti_totali_attuali=650000.0,
    )
    assert res_sopra["e_impresa_minore"] is False
    assert "Composizione Negoziata" in res_sopra["procedure_esperibili"][0]


def test_ccii_segnali_allarme_art3():
    # Allarme AdER art. 25-novies (> 500k per capitali)
    alert = check_ccii_segnali_allarme_art3(
        retribuzioni_scadute_30gg=0.0,
        monte_salari_mensile=20000.0,
        debiti_fornitori_scaduti_90gg=0.0,
        debiti_fornitori_non_scaduti=50000.0,
        esposizioni_banche_scadute_60gg=0.0,
        sconfinamento_banche_fidi=0.0,
        totale_fidi_accordati=100000.0,
        debiti_ader_scaduti_90gg=550000.0,
        tipo_soggetto="societa_capitali",
    )
    assert alert["ha_segnali_allarme_art3"] is True
    assert alert["segnali"][0]["codice"] == "art25_novies_ader"

