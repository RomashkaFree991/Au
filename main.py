import asyncio
import json
import logging
import os
import time
from pathlib import Path

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, MessageEntity
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@tonkursika")

# Необязательно. Если хочешь, чтобы только ты мог настраивать эмодзи:
# ADMIN_USER_ID=8667321828
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0") or 0)

TON_ID = "the-open-network"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"

POST_INTERVAL_SECONDS = 300  # 5 минут
CONFIG_FILE = Path("emoji_config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

dp = Dispatcher()
last_post_time = 0.0


EMOJI_ORDER = [
    ("ton", "TON"),
    ("rub", "рубля"),
    ("usd", "доллара / USDT"),
]


def load_emoji_config() -> dict:
    if not CONFIG_FILE.exists():
        return {"ton": "", "rub": "", "usd": ""}

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"ton": "", "rub": "", "usd": ""}

    return {
        "ton": str(data.get("ton", "")).strip(),
        "rub": str(data.get("rub", "")).strip(),
        "usd": str(data.get("usd", "")).strip(),
    }


def save_emoji_config(config: dict) -> None:
    CONFIG_FILE.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def emoji_config_ready(config: dict) -> bool:
    return (
        config.get("ton", "").isdigit()
        and config.get("rub", "").isdigit()
        and config.get("usd", "").isdigit()
    )


def get_next_missing_emoji(config: dict):
    for key, name in EMOJI_ORDER:
        if not config.get(key, "").isdigit():
            return key, name
    return None, None


def is_admin(message: Message) -> bool:
    if ADMIN_USER_ID == 0:
        return True

    return message.from_user and message.from_user.id == ADMIN_USER_ID


def extract_custom_emoji_id(message: Message) -> str | None:
    # Когда ты отправляешь премиум-эмодзи как текст
    if message.entities:
        for entity in message.entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                return str(entity.custom_emoji_id)

    # Когда эмодзи отправлена в подписи
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == "custom_emoji" and entity.custom_emoji_id:
                return str(entity.custom_emoji_id)

    # Когда отправлен именно custom emoji sticker
    if message.sticker and message.sticker.custom_emoji_id:
        return str(message.sticker.custom_emoji_id)

    return None


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


def utf16_offset(text: str, char_index: int) -> int:
    return len(text[:char_index].encode("utf-16-le")) // 2


def utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def build_text_with_entities(rub: str, usd: str, config: dict):
    # Заглушки будут заменены премиум-эмодзи через MessageEntity
    text = f"1 💎 = {rub} ₽ = {usd} $"

    placeholders = [
        ("💎", config["ton"]),
        ("₽", config["rub"]),
        ("$", config["usd"]),
    ]

    entities = []

    for symbol, custom_emoji_id in placeholders:
        char_index = text.index(symbol)

        entities.append(
            MessageEntity(
                type="custom_emoji",
                offset=utf16_offset(text, char_index),
                length=utf16_length(symbol),
                custom_emoji_id=custom_emoji_id
            )
        )

    return text, entities


async def send_ton_rate(bot: Bot) -> None:
    global last_post_time

    config = load_emoji_config()

    if not emoji_config_ready(config):
        logging.info("Эмодзи ещё не настроены. Автопостинг не начат.")
        return

    price = await get_ton_price()

    rub = format_price(price["rub"], 2)
    usd = format_price(price["usd"], 4)

    text, entities = build_text_with_entities(rub, usd, config)

    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        entities=entities
    )

    last_post_time = time.monotonic()
    logging.info("Курс TON отправлен в канал")


async def auto_posting(bot: Bot) -> None:
    global last_post_time

    while True:
        try:
            config = load_emoji_config()

            if emoji_config_ready(config):
                now = time.monotonic()

                if last_post_time == 0 or now - last_post_time >= POST_INTERVAL_SECONDS:
                    await send_ton_rate(bot)

        except Exception as error:
            logging.exception(f"Ошибка автопостинга: {error}")

        await asyncio.sleep(5)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    # На /start бот ничего не отвечает
    return


@dp.message(Command("resetemoji"))
async def reset_emoji_handler(message: Message) -> None:
    global last_post_time

    if not is_admin(message):
        return

    save_emoji_config({"ton": "", "rub": "", "usd": ""})
    last_post_time = 0

    await message.answer(
        "Эмодзи сброшены.\n"
        "Теперь отправь по очереди:\n"
        "1) эмодзи TON\n"
        "2) эмодзи рубля\n"
        "3) эмодзи доллара / USDT"
    )


@dp.message(F.entities | F.caption_entities | F.sticker)
async def setup_emoji_handler(message: Message, bot: Bot) -> None:
    if not is_admin(message):
        return

    custom_emoji_id = extract_custom_emoji_id(message)

    if not custom_emoji_id:
        await message.answer(
            "Это не premium/custom emoji.\n"
            "Нужна именно премиум-эмодзи, не обычный file_id вида CAAC..."
        )
        return

    if not custom_emoji_id.isdigit():
        await message.answer(
            "Telegram вернул не числовой custom_emoji_id.\n"
            "Попробуй отправить именно премиум-эмодзи как текст, а не file_id."
        )
        return

    config = load_emoji_config()
    key, name = get_next_missing_emoji(config)

    if not key:
        await message.answer(
            "Все 3 эмодзи уже сохранены.\n"
            "Если хочешь настроить заново, напиши /resetemoji"
        )
        return

    config[key] = custom_emoji_id
    save_emoji_config(config)

    next_key, next_name = get_next_missing_emoji(config)

    if next_key:
        await message.answer(
            f"Сохранил эмодзи {name}.\n"
            f"Теперь отправь эмодзи {next_name}."
        )
    else:
        await message.answer(
            "Все эмодзи сохранены ✅\n"
            "Автопостинг запущен."
        )

        await send_ton_rate(bot)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN в .env")

    bot = Bot(token=BOT_TOKEN)

    asyncio.create_task(auto_posting(bot))

    logging.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())