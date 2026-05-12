import asyncio
import logging
import os

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, MessageEntity
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@tonkursika")

# Сюда надо вставить именно custom_emoji_id, НЕ CAAC...
TON_EMOJI_ID = os.getenv("TON_EMOJI_ID", "").strip()
RUB_EMOJI_ID = os.getenv("RUB_EMOJI_ID", "").strip()
USD_EMOJI_ID = os.getenv("USD_EMOJI_ID", "").strip()

TON_ID = "the-open-network"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

POST_INTERVAL_SECONDS = 300

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
        raise ValueError(f"CoinGecko не вернул TON: {data}")

    return ton_data


def format_price(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}".replace(",", " ")


def build_text_with_entities(rub: str, usd: str):
    # Обычные символы-заглушки: они будут заменены премиум-эмодзи через entities
    text = f"1 💎 = {rub} ₽ = {usd} $"

    entities = []

    ton_offset = text.index("💎")
    rub_offset = text.index("₽")
    usd_offset = text.index("$")

    if TON_EMOJI_ID:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=ton_offset,
                length=2,
                custom_emoji_id=TON_EMOJI_ID
            )
        )

    if RUB_EMOJI_ID:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=rub_offset,
                length=1,
                custom_emoji_id=RUB_EMOJI_ID
            )
        )

    if USD_EMOJI_ID:
        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=usd_offset,
                length=1,
                custom_emoji_id=USD_EMOJI_ID
            )
        )

    return text, entities


async def send_ton_rate(bot: Bot) -> None:
    price = await get_ton_price()

    rub = format_price(price["rub"], 2)
    usd = format_price(price["usd"], 4)

    text, entities = build_text_with_entities(rub, usd)

    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        entities=entities
    )

    logging.info("Курс TON отправлен")


async def auto_posting(bot: Bot) -> None:
    while True:
        try:
            await send_ton_rate(bot)
        except Exception as error:
            logging.exception(f"Ошибка автопостинга: {error}")

        await asyncio.sleep(POST_INTERVAL_SECONDS)


# Бот ничего не отвечает, только выводит ID в консоль
@dp.message(F.entities)
async def catch_custom_emoji_id(message: Message) -> None:
    for entity in message.entities:
        if entity.type == "custom_emoji":
            logging.info(f"CUSTOM_EMOJI_ID={entity.custom_emoji_id}")


@dp.message(F.sticker)
async def catch_sticker(message: Message) -> None:
    logging.info(f"STICKER_FILE_ID={message.sticker.file_id}")

    if message.sticker.custom_emoji_id:
        logging.info(f"CUSTOM_EMOJI_ID={message.sticker.custom_emoji_id}")


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN в .env")

    bot = Bot(token=BOT_TOKEN)

    asyncio.create_task(auto_posting(bot))

    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())