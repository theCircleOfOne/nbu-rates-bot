from bot import menu
from bot.logic import MAIN_CURRENCIES, parse_hhmm


def _buttons(kb):
    return [b for row in kb.inline_keyboard for b in row]


def test_callback_data_within_telegram_limit():
    for kb in (menu.main_menu(), menu.rates_menu(), menu.convert_menu(), menu.daily_menu(), menu.cancel_menu()):
        for b in _buttons(kb):
            assert b.callback_data and len(b.callback_data.encode()) <= 64


def test_main_menu_layout():
    rows = menu.main_menu().inline_keyboard
    assert [len(r) for r in rows] == [1, len(MAIN_CURRENCIES), 1, 1]
    assert {b.callback_data for b in _buttons(menu.main_menu())} >= {
        "menu:rates", "menu:conv", "menu:daily", "rate:USD",
    }


def test_daily_buttons_carry_valid_times():
    times = [b.callback_data.removeprefix("daily:set:") for b in _buttons(menu.daily_menu())
             if b.callback_data.startswith("daily:set:")]
    assert times == list(menu.DAILY_TIMES)
    assert all(parse_hhmm(t) == t for t in times)


def test_every_submenu_has_back_button():
    for kb in (menu.rates_menu(), menu.convert_menu(), menu.daily_menu()):
        assert "menu:main" in {b.callback_data for b in _buttons(kb)}
