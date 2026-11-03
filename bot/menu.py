"""Inline keyboards. Callback data scheme (<= 64 bytes, Telegram limit):

    menu:main | menu:rates | menu:daily
    rate:<CC>            show one currency
    conv:<CC>            start conversion of <CC> to UAH
    daily:set:<HH:MM> | daily:off
"""
from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .logic import MAIN_CURRENCIES

DAILY_TIMES = ("08:00", "09:00", "12:00", "18:00")
BACK = ("« Меню", "menu:main")


def _build(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for row in rows:
        for text, data in row:
            b.button(text=text, callback_data=data)
    b.adjust(*(len(r) for r in rows))
    return b.as_markup()


def main_menu() -> InlineKeyboardMarkup:
    return _build([
        [("📊 Курси НБУ", "menu:rates")],
        [(cc, f"rate:{cc}") for cc in MAIN_CURRENCIES],
        [("💱 Конвертер", "menu:conv")],
        [("⏰ Щоденна розсилка", "menu:daily")],
    ])


def rates_menu() -> InlineKeyboardMarkup:
    return _build([[(cc, f"rate:{cc}") for cc in MAIN_CURRENCIES], [BACK]])


def convert_menu() -> InlineKeyboardMarkup:
    return _build([[(cc, f"conv:{cc}") for cc in MAIN_CURRENCIES], [BACK]])


def daily_menu() -> InlineKeyboardMarkup:
    return _build([
        [(t, f"daily:set:{t}") for t in DAILY_TIMES],
        [("🔕 Вимкнути", "daily:off")],
        [BACK],
    ])


def cancel_menu() -> InlineKeyboardMarkup:
    return _build([[("Скасувати", "menu:main")]])
