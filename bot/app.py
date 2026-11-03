"""aiogram handlers (commands + inline menu) and daily digest scheduler."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, InlineKeyboardMarkup, Message

from . import menu
from .logic import UserError, convert, format_rate, format_rates, parse_hhmm
from .nbu import NbuClient
from .storage import Subscriptions

TZ = ZoneInfo("Europe/Kyiv")
log = logging.getLogger("nbu-bot")

HELP = (
    "Курси валют НБУ\n\n"
    "Користуйтесь кнопками нижче або командами:\n"
    "/rates — USD, EUR, PLN, GBP\n"
    "/rate USD — курс однієї валюти\n"
    "/convert 100 USD — у гривні\n"
    "/convert 1000 UAH EUR — з гривні\n"
    "/daily 09:00 — щоденна розсилка (за київським часом)\n"
    "/stop — скасувати розсилку"
)

COMMANDS = [
    BotCommand(command="menu", description="Головне меню"),
    BotCommand(command="rates", description="Курси USD, EUR, PLN, GBP"),
    BotCommand(command="rate", description="Курс однієї валюти: /rate USD"),
    BotCommand(command="convert", description="Конвертер: /convert 100 USD"),
    BotCommand(command="daily", description="Щоденна розсилка: /daily 09:00"),
    BotCommand(command="stop", description="Скасувати розсилку"),
]


class ConvertFlow(StatesGroup):
    amount = State()  # waiting for the amount; chosen currency lives in FSM data


async def _show(cb: CallbackQuery, text: str, kb: InlineKeyboardMarkup) -> None:
    """Edit the menu message in place; ignore Telegram's 'message is not modified'."""
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc):
            raise
    await cb.answer()


def build_router(nbu: NbuClient, subs: Subscriptions) -> Router:
    router = Router()

    def subscribe(chat_id: int, hhmm: str) -> str:
        now = datetime.now(TZ)
        subs.set_daily(chat_id, hhmm, now.strftime("%H:%M"), now.date().isoformat())
        return f"Готово: щодня о {hhmm} (Київ) надсилатиму курси."

    # ---- commands ----
    @router.message(Command("start", "help", "menu"))
    async def start(m: Message, state: FSMContext) -> None:
        await state.clear()
        await m.answer(HELP, reply_markup=menu.main_menu())

    @router.message(Command("rates"))
    async def rates(m: Message) -> None:
        await m.answer(format_rates(await nbu.get_rates()))

    @router.message(Command("rate"))
    async def rate(m: Message, command: CommandObject) -> None:
        cc = (command.args or "USD").strip().upper()
        data = await nbu.get_rates()
        if cc not in data:
            raise UserError(f"Валюту {cc} не знайдено в курсах НБУ.")
        await m.answer(format_rate(data[cc]))

    @router.message(Command("convert"))
    async def conv(m: Message, command: CommandObject) -> None:
        await m.answer(convert((command.args or "").split(), await nbu.get_rates()))

    @router.message(Command("daily"))
    async def daily(m: Message, command: CommandObject) -> None:
        await m.answer(subscribe(m.chat.id, parse_hhmm(command.args or "")))

    @router.message(Command("stop"))
    async def stop(m: Message) -> None:
        await m.answer("Розсилку скасовано." if subs.remove(m.chat.id) else "Розсилка не була активна.")

    # ---- menu buttons ----
    @router.callback_query(F.data == "menu:main")
    async def cb_main(cb: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await _show(cb, HELP, menu.main_menu())

    @router.callback_query(F.data == "menu:rates")
    async def cb_rates(cb: CallbackQuery) -> None:
        await _show(cb, format_rates(await nbu.get_rates()), menu.rates_menu())

    @router.callback_query(F.data.startswith("rate:"))
    async def cb_rate(cb: CallbackQuery) -> None:
        cc = cb.data.split(":", 1)[1]
        data = await nbu.get_rates()
        if cc not in data:
            raise UserError(f"Валюту {cc} не знайдено в курсах НБУ.")
        await _show(cb, format_rate(data[cc]), menu.rates_menu())

    @router.callback_query(F.data == "menu:conv")
    async def cb_conv_menu(cb: CallbackQuery) -> None:
        await _show(cb, "Яку валюту переводимо в гривню?", menu.convert_menu())

    @router.callback_query(F.data.startswith("conv:"))
    async def cb_conv_pick(cb: CallbackQuery, state: FSMContext) -> None:
        cc = cb.data.split(":", 1)[1]
        await state.set_state(ConvertFlow.amount)
        await state.update_data(cc=cc)
        await _show(cb, f"Введіть суму в {cc} (наприклад 250):", menu.cancel_menu())

    @router.message(ConvertFlow.amount, F.text, ~F.text.startswith("/"))
    async def conv_amount(m: Message, state: FSMContext) -> None:
        cc = (await state.get_data())["cc"]
        text = convert([m.text, cc], await nbu.get_rates())  # UserError keeps the state
        await state.clear()
        await m.answer(text, reply_markup=menu.main_menu())

    @router.callback_query(F.data == "menu:daily")
    async def cb_daily_menu(cb: CallbackQuery) -> None:
        await _show(cb, "О котрій надсилати курси щодня? (Київ)\nІнший час: /daily HH:MM", menu.daily_menu())

    @router.callback_query(F.data.startswith("daily:set:"))
    async def cb_daily_set(cb: CallbackQuery) -> None:
        hhmm = parse_hhmm(cb.data.removeprefix("daily:set:"))
        await _show(cb, subscribe(cb.message.chat.id, hhmm), menu.main_menu())

    @router.callback_query(F.data == "daily:off")
    async def cb_daily_off(cb: CallbackQuery) -> None:
        text = "Розсилку скасовано." if subs.remove(cb.message.chat.id) else "Розсилка не була активна."
        await _show(cb, text, menu.main_menu())

    # ---- errors ----
    @router.error()
    async def on_error(event) -> bool:
        exc = event.exception
        message = getattr(event.update, "message", None)
        cb = getattr(event.update, "callback_query", None)
        shown = str(exc) if isinstance(exc, UserError) else "Сталася помилка, спробуйте пізніше."
        if not isinstance(exc, UserError):
            log.exception("Unhandled error", exc_info=exc)
        if message:
            await message.answer(shown)
        elif cb:
            await cb.answer(shown, show_alert=True)
        return True

    return router


async def digest_loop(bot: Bot, nbu: NbuClient, subs: Subscriptions, tick_s: int = 30) -> None:
    while True:
        try:
            now = datetime.now(TZ)
            due = subs.due(now.strftime("%H:%M"), now.date().isoformat())
            if due:
                text = format_rates(await nbu.get_rates())
                for chat_id in due:
                    try:
                        await bot.send_message(chat_id, text)
                        subs.mark_sent(chat_id, now.date().isoformat())
                    except Exception:  # blocked bot, deleted chat, etc.
                        log.warning("send failed for %s", chat_id, exc_info=True)
        except Exception:
            log.exception("digest tick failed")
        await asyncio.sleep(tick_s)


async def run(token: str, db_path: str = "subs.db") -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(token, default=DefaultBotProperties(parse_mode=None))
    await bot.set_my_commands(COMMANDS)
    async with aiohttp.ClientSession() as session:
        nbu, subs = NbuClient(session), Subscriptions(db_path)
        dp = Dispatcher()  # in-memory FSM storage: conversion state is short-lived
        dp.include_router(build_router(nbu, subs))
        task = asyncio.create_task(digest_loop(bot, nbu, subs))
        try:
            await dp.start_polling(bot)
        finally:
            task.cancel()
            await bot.session.close()
