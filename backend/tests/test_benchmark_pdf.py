import io
import pdfplumber
import pytest
from app.services.benchmark_pdf_generator import generate_benchmark_7page_pdf


def test_benchmark_pdf_seven_pages():
    data = {
        "header": {
            "cliente": "LUCREZIA D'AMICO",
            "forma_giuridica": "Ditta individuale artigiana · Palermo",
            "data_bozza": "09.11.2026",
        }
    }
    pdf_bytes = generate_benchmark_7page_pdf(data)
    assert len(pdf_bytes) > 10000

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as reader:
        assert len(reader.pages) == 7

        # Verifica intestazioni delle 7 sezioni
        p1 = reader.pages[0].extract_text()
        assert "RELAZIONE FINALE DI PRE-ANALISI" in p1
        assert "493.094" in p1
        assert "523.101" in p1

        p2 = reader.pages[1].extract_text()
        assert "01 / PROFILO E CONTO ECONOMICO" in p2
        assert "Ricavi e proventi" in p2

        p3 = reader.pages[2].extract_text()
        assert "02 / INDEBITAMENTO RICOSTRUITO" in p3
        assert "523.100,79" in p3

        p4 = reader.pages[3].extract_text()
        assert "03 / PATRIMONIO E CONFRONTO LIQUIDATORIO" in p4
        assert "20.000" in p4

        p5 = reader.pages[4].extract_text()
        assert "04 / REDDITIVITÀ E CONTINUITÀ" in p5
        assert "EBITDA quadrimestre" in p5

        p6 = reader.pages[5].extract_text()
        assert "05 / INQUADRAMENTO CCII" in p6
        assert "art. 2, comma 1, lett. d" in p6

        p7 = reader.pages[6].extract_text()
        assert "06 / CONCLUSIONI E PROPOSTA DI INCARICO" in p7
        assert "COMPOSIZIONE NEGOZIATA" in p7
