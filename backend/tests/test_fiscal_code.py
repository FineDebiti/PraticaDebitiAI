import pytest
from app.services import fiscal_code as fc


def test_normalize():
    assert fc.normalize(" rss mra 80a01 h501u ") == "RSSMRA80A01H501U"
    assert fc.normalize("12345678901") == "12345678901"
    assert fc.normalize("") == ""
    assert fc.normalize(None) == ""


def test_is_valid_format():
    assert fc.is_valid_format("RSSMRA80A01H501U") is True
    assert fc.is_valid_format("12345678901") is True
    assert fc.is_valid_format("INVALID") is False
    assert fc.is_valid_format("12345") is False
    assert fc.is_valid_format("") is False


def test_same():
    assert fc.same("RSSMRA80A01H501U", "rssmra80a01h501u") is True
    assert fc.same("12345678901", "12345678901") is True
    assert fc.same("RSSMRA80A01H501U", "RSSMRA80A01H502Z") is False
    assert fc.same("", "") is False
