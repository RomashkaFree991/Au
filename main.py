import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@tonkursika")

TON_ID = "the-open-network"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

POST_INTERVAL_SECONDS = 300  # 5 минут

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

dp = Dispatcher()


async def get_ton_price() -> dict:
    params = {
        "ids": TON_ID,
        "vs_currencies": "rub,usd",
        "include_last_updated_at": "true",
        "precision": "full",
    }

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(COINGECKO_URL, params=params)
        response.raise_for_status()
        data = response.json()

    ton_data = data.get(TON_ID)

    if not ton_data:
        raise ValueError(f"CoinGecko не вернул данные по TON: {data}")

    return ton_data


def format_updated_time(timestamp: int | None) -> str:
    if not timestamp:
        return "неизвестно"

    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.strftime("%d.%m.%Y %H:%M UTC")


def format_price(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", " ")


async def send_ton_rate(bot: Bot) -> None:
    price = await get_ton_price()

    rub = price["rub"]
    usd = price["usd"]
    updated_at = format_updated_time(price.get("last_updated_at"))

    text = (
        "💎 Курс TON\n\n"
        f"1 TON = {format_price(rub, 2)} ₽\n"
        f"1 TON = ${format_price(usd, 4)}\n\n"
        f"Обновлено: {updated_at}"
    )

    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=text
    )

    logging.info("Курс TON отправлен в канал")


async def auto_posting(bot: Bot) -> None:
    while True:
        try:
            await send_ton_rate(bot)
        except Exception as error:
            logging.exception(f"Ошибка автопостинга: {error}")

        await asyncio.sleep(POST_INTERVAL_SECONDS)


@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer("Бот запущен. Он публикует курс TON каждые 5 минут.")


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN в .env")

    bot = Bot(token=BOT_TOKEN)

    asyncio.create_task(auto_posting(bot))

    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())