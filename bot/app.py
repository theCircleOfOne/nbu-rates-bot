"""aiogram handlers + daily digest scheduler."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from .logic import UserError, convert, format_rate, format_rates, parse_hhmm
from .nbu import NbuClient
from .storage import Subscriptions

TZ = ZoneInfo("Europe/Kyiv")
log = logging.getLogger("nbu-bot")

HELP = (
    "Курси валют НБУ\n\n"
    "/rates — USD, EUR, PLN, GBP\n"
    "/rate USD — курс однієї валюти\n"
    "/convert 100 USD — у гривні\n"
    "/convert 1000 UAH EUR — з гривні\n"
    "/daily 09:00 — щоденна розсилка (за київським часом)\n"
    "/stop — скасувати розсилку"
)


def build_router(nbu: NbuClient, subs: Subscriptions) -> Router:
    router = Router()

    @router.message(Command("start", "help"))
    async def start(m: Message) -> None:
        await m.answer(HELP)

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
        hhmm = parse_hhmm(command.args or "")
        now = datetime.now(TZ)
        subs.set_daily(m.chat.id, hhmm, now.strftime("%H:%M"), now.date().isoformat())
        await m.answer(f"Готово: щодня о {hhmm} (Київ) надсилатиму курси.")

    @router.message(Command("stop"))
    async def stop(m: Message) -> None:
        await m.answer("Розсилку скасовано." if subs.remove(m.chat.id) else "Розсилка не була активна.")

    @router.error()
    async def on_error(event) -> bool:
        exc = event.exception
        message = getattr(event.update, "message", None)
        if isinstance(exc, UserError):
            if message:
                await message.answer(str(exc))
            return True
        log.exception("Unhandled error", exc_info=exc)
        if message:
            await message.answer("Сталася помилка, спробуйте пізніше.")
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
    async with aiohttp.ClientSession() as session:
        nbu, subs = NbuClient(session), Subscriptions(db_path)
        dp = Dispatcher()
        dp.include_router(build_router(nbu, subs))
        task = asyncio.create_task(digest_loop(bot, nbu, subs))
        try:
            await dp.start_polling(bot)
        finally:
            task.cancel()
            await bot.session.close()
