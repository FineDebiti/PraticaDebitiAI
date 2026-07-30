import pytest
from app.services.indicators import compute_indicators, _safe_div, _pct, _trend


def test_safe_div():
    assert _safe_div(100.0, 50.0) == 2.0
    assert _safe_div(100.0, 0.0) is None
    assert _safe_div(None, 50.0) is None
    assert _safe_div(100.0, None) is None


def test_pct():
    assert _pct(0.15) == 15.0
    assert _pct(0.0) == 0.0
    assert _pct(None) is None


def test_trend():
    assert _trend(10.0, 5.0) == "up"
    assert _trend(5.0, 10.0) == "down"
    assert _trend(5.0, 5.0) == "flat"
    assert _trend(None, 5.0) == "na"


def test_compute_indicators_standard():
    sp = {
        "totale_attivo_circolante": {"corrente": 150000.0, "precedente": 100000.0},
        "rimanenze": {"corrente": 30000.0, "precedente": 20000.0},
        "debiti_entro": {"corrente": 100000.0, "precedente": 80000.0},
        "totale_attivo": {"corrente": 300000.0, "precedente": 250000.0},
        "patrimonio_netto": {"corrente": 100000.0, "precedente": 80000.0},
        "debiti_totali": {"corrente": 180000.0, "precedente": 150000.0},
        "disponibilita_liquide": {"corrente": 20000.0, "precedente": 10000.0},
        "totale_immobilizzazioni": {"corrente": 150000.0, "precedente": 150000.0},
    }
    ce = {
        "ricavi_vendite": {"corrente": 400000.0, "precedente": 350000.0},
        "differenza_valore_costi": {"corrente": 40000.0, "precedente": 30000.0},
        "utile_perdita": {"corrente": 20000.0, "precedente": 15000.0},
        "oneri_finanziari": {"corrente": 5000.0, "precedente": 4000.0},
    }
    deb = {
        "tributari": {"importo": 10000.0},
        "previdenziali": {"importo": 5000.0},
    }

    indicators = compute_indicators(sp, ce, deb)
    by_code = {ind["code"]: ind for ind in indicators}

    # Current ratio = 150k / 100k = 1.5
    assert by_code["current_ratio"]["value_cur"] == 1.5
    # Acid test = (150k - 30k) / 100k = 1.2
    assert by_code["acid_test"]["value_cur"] == 1.2
    # ROE = 20k / 100k * 100 = 20%
    assert by_code["roe"]["value_cur"] == 20.0
    # Leva = 180k / 100k = 1.8
    assert by_code["leva"]["value_cur"] == 1.8
    # ROS = 40k / 400k * 100 = 10%
    assert by_code["ros"]["value_cur"] == 10.0


def test_compute_indicators_zero_division_guard():
    sp = {"debiti_entro": {"corrente": 0.0}}
    ce = {}
    deb = {}
    indicators = compute_indicators(sp, ce, deb)
    by_code = {ind["code"]: ind for ind in indicators}
    assert by_code["current_ratio"]["value_cur"] is None
    assert by_code["current_ratio"]["status"] == "na"
