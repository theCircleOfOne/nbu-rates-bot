# nbu-rates-bot

Telegram bot with official **NBU (National Bank of Ukraine)** exchange rates:
instant lookups, UAH conversion and an optional daily digest at a time you choose.
Built with Python 3.12 and aiogram 3 (async). The bot UI is in Ukrainian.

## Commands
| Command | What it does |
|---|---|
| `/rates` | USD, EUR, PLN, GBP |
| `/rate USD` | one currency (any code from the NBU list, 45 currencies) |
| `/convert 100 USD` | foreign currency to UAH |
| `/convert 1000 UAH EUR` | UAH to foreign currency |
| `/daily 09:00` | daily digest at 09:00 Kyiv time |
| `/stop` | cancel the digest |

## What it shows
- Async bot with a background scheduler for daily messages (Europe/Kyiv time zone)
- Public API client with response caching and tolerant parsing (decimal commas)
- User-input validation with friendly error messages; unexpected errors are logged, not leaked
- Business logic separated from Telegram code, so it is covered by offline unit tests (12 tests)
- Subscriptions in SQLite; a subscriber is never sent the same digest twice in a day,
  and a late subscriber does not get an immediate message for a time that has already passed

## Run (PowerShell)
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # put the token from @BotFather into BOT_TOKEN
python -m bot
pytest
```

## Structure
```
bot/nbu.py       NBU API client + cache
bot/logic.py     parsing, conversion, message formatting (pure functions)
bot/storage.py   SQLite subscriptions
bot/app.py       aiogram handlers + digest scheduler
tests/           unit tests
```

## Notes
- Rates are the official NBU rates (UAH per 1 unit) published once per working day.
- Data source: https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange
- Custom Telegram bots (orders, forms, payments, CRM / Google Sheets integration) are available on request.
