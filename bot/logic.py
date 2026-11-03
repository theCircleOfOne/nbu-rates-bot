"""Pure helpers: argument parsing, conversion, message formatting (no I/O)."""
from __future__ import annotations

import re

from .nbu import Rate

MAIN_CURRENCIES = ("USD", "EUR", "PLN", "GBP")
_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class UserError(ValueError):
    """Message is safe to show to the end user."""


def parse_hhmm(text: str) -> str:
    """'9:05' -> '09:05'. Raises UserError on bad input."""
    m = _HHMM.match(text.strip())
    if not m:
        raise UserError("Формат часу: HH:MM, наприклад /daily 09:00")
    return f"{int(m.group(1)):02d}:{m.group(2)}"


def _amount(text: str) -> float:
    try:
        value = float(text.replace(",", ".").replace(" ", ""))
    except ValueError:
        raise UserError(f"«{text}» — не число.") from None
    if value <= 0 or value > 1e12:
        raise UserError("Сума має бути додатною та розумною.")
    return value


def _rate(rates: dict[str, Rate], cc: str) -> Rate:
    r = rates.get(cc.upper())
    if r is None:
        raise UserError(f"Валюту {cc.upper()} не знайдено в курсах НБУ.")
    return r


def convert(args: list[str], rates: dict[str, Rate]) -> str:
    """`100 USD` -> UAH;  `1000 UAH EUR` -> EUR."""
    if len(args) == 2:
        amount, r = _amount(args[0]), _rate(rates, args[1])
        return f"{amount:,.2f} {r.cc} = {amount * r.rate:,.2f} UAH\n(курс НБУ {r.rate:.4f}, {r.date})"
    if len(args) == 3 and args[1].upper() == "UAH":
        amount, r = _amount(args[0]), _rate(rates, args[2])
        return f"{amount:,.2f} UAH = {amount / r.rate:,.2f} {r.cc}\n(курс НБУ {r.rate:.4f}, {r.date})"
    raise UserError("Приклади:\n/convert 100 USD\n/convert 1000 UAH EUR")


def format_rate(r: Rate) -> str:
    return f"{r.cc} ({r.name}): {r.rate:.4f} UAH\nНа {r.date}"


def format_rates(rates: dict[str, Rate], codes: tuple[str, ...] = MAIN_CURRENCIES) -> str:
    rows = [f"{c}: {rates[c].rate:.4f}" for c in codes if c in rates]
    if not rows:
        raise UserError("Курси тимчасово недоступні.")
    date = rates[next(c for c in codes if c in rates)].date
    return f"Офіційні курси НБУ на {date} (UAH):\n" + "\n".join(rows)
