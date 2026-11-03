"""python -m bot  (reads BOT_TOKEN from environment or .env)"""
import asyncio
import os

from dotenv import load_dotenv

from .app import run

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(run(os.environ["BOT_TOKEN"], os.getenv("DB_PATH", "subs.db")))
