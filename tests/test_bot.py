import pytest

from bot.logic import UserError, convert, format_rates, parse_hhmm
from bot.nbu import parse_rates
from bot.storage import Subscriptions

PAYLOAD = [
    {"r030": 840, "txt": "Долар США", "rate": 45.666, "cc": "USD", "exchangedate": "04.11.2026"},
    {"r030": 978, "txt": "Євро", "rate": "51,0582", "cc": "EUR", "exchangedate": "04.11.2026"},
]
RATES = parse_rates(PAYLOAD)


def test_parse_rates_handles_decimal_comma():
    assert RATES["EUR"].rate == pytest.approx(51.0582)
    assert RATES["USD"].date == "04.11.2026"


def test_convert_to_uah():
    # 100 USD * 45.666 = 4566.60 UAH
    assert "4,566.60 UAH" in convert(["100", "usd"], RATES)


def test_convert_from_uah():
    # 1000 / 51.0582 = 19.5858... EUR
    assert "19.59 EUR" in convert(["1000", "UAH", "EUR"], RATES)


@pytest.mark.parametrize("args", [[], ["abc", "USD"], ["-5", "USD"], ["10", "XXX"], ["1", "2", "3", "4"]])
def test_convert_rejects_bad_input(args):
    with pytest.raises(UserError):
        convert(args, RATES)


def test_parse_hhmm():
    assert parse_hhmm("9:05") == "09:05"
    for bad in ("", "24:00", "09:60", "abc"):
        with pytest.raises(UserError):
            parse_hhmm(bad)


def test_format_rates_lists_available_only():
    text = format_rates(RATES)
    assert "USD: 45.6660" in text and "EUR: 51.0582" in text and "PLN" not in text


def test_daily_due_logic(tmp_path):
    s = Subscriptions(tmp_path / "t.db")
    today = "2026-11-04"
    # subscribe for 09:00 while it is 10:00 -> today's digest is skipped
    s.set_daily(1, "09:00", now_hhmm="10:00", today=today)
    # subscribe for 15:00 while it is 10:00 -> due later today
    s.set_daily(2, "15:00", now_hhmm="10:00", today=today)
    assert s.due("10:00", today) == []
    assert s.due("15:00", today) == [2]
    s.mark_sent(2, today)
    assert s.due("15:30", today) == []
    # next day both are due again once their time passes
    assert sorted(s.due("23:00", "2026-11-05")) == [1, 2]


def test_remove(tmp_path):
    s = Subscriptions(tmp_path / "t.db")
    s.set_daily(1, "09:00", "08:00", "2026-11-04")
    assert s.remove(1) is True
    assert s.remove(1) is False
