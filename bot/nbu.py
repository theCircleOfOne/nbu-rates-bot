"""NBU (National Bank of Ukraine) open API client: official UAH exchange rates."""
from __future__ import annotations

import time
from dataclasses import dataclass

import aiohttp

API_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
CACHE_TTL_S = 600


@dataclass(frozen=True)
class Rate:
    cc: str      # ISO code, e.g. "USD"
    name: str    # Ukrainian name
    rate: float  # UAH per 1 unit of currency
    date: str    # dd.mm.yyyy, date the rate is valid for


def parse_rates(payload: list[dict]) -> dict[str, Rate]:
    """Map raw NBU JSON to {cc: Rate}. Tolerates decimal commas."""
    out: dict[str, Rate] = {}
    for item in payload:
        cc = str(item["cc"]).upper()
        out[cc] = Rate(
            cc=cc,
            name=item.get("txt", cc),
            rate=float(str(item["rate"]).replace(",", ".")),
            date=item["exchangedate"],
        )
    return out


class NbuClient:
    """Fetches rates with a small in-memory cache (NBU updates them once a day)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._cache: tuple[float, dict[str, Rate]] | None = None

    async def get_rates(self) -> dict[str, Rate]:
        now = time.monotonic()
        if self._cache and now - self._cache[0] < CACHE_TTL_S:
            return self._cache[1]
        async with self._session.get(
            API_URL, params={"json": ""}, timeout=aiohttp.ClientTimeout(total=15)
        ) as resp:
            resp.raise_for_status()
            rates = parse_rates(await resp.json(content_type=None))
        self._cache = (now, rates)
        return rates
