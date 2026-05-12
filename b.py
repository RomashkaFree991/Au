import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, ErrorEvent
from aiogram.exceptions import TelegramForbiddenError

# === НАСТРОЙКИ ===
BOT_TOKEN = "8593674356:AAEIc-t6XVxdXr80uvKdbgPLDD3Ra8ZexxU"
ADMIN_ID = 8667321828
TARGET_GIFT_ID = 333000 # Айди служебных уведомлений
GIFT_ID = "5170233102089322756" # Айди мишки
PASS_PRICE = 10 # Цена проходки в звездах
REF_GOAL = 10 # Сколько людей нужно пригласить для мишки

router = Router()
bot = Bot(token=BOT_TOKEN)

# Временная "база данных"
users_db = {}

def get_user(user_id):
    if user_id not in users_db:
        users_db[user_id] = {
            "paid": False, 
            "invited_by": None, 
            "refs_paid": 0, 
            "refs_total": 0, 
            "bear_received": False
        }
    return users_db[user_id]

# === ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК ===
# Если юзер заблокировал бота, мы просто игнорируем ошибку, чтобы консоль не спамила
@router.error()
async def on_error(event: ErrorEvent):
    if isinstance(event.exception, TelegramForbiddenError):
        print(f"Игнорируем ошибку: пользователь заблокировал бота.")
    else:
        print(f"Произошла неизвестная ошибка: {event.exception}")

# === ФУНКЦИЯ ОТПРАВКИ ПОДАРКА ЧЕРЕЗ API ===
async def send_gift_to_api(user_id, gift_id, text=""):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendGift"
    payload = {"user_id": user_id, "gift_id": gift_id, "text": text}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            result = await response.json()
            return result.get("ok", False)

# === ХЭНДЛЕРЫ ===

# 1. Команда /start
@router.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    user = get_user(message.from_user.id)
    
    if command.args and command.args.startswith("ref_"):
        try:
            inviter_id = int(command.args.split("_")[1])
            if inviter_id != message.from_user.id and not user["paid"] and user["invited_by"] is None:
                user["invited_by"] = inviter_id
                inviter = get_user(inviter_id)
                inviter["refs_total"] += 1
        except:
            pass

    if user["paid"]:
        await send_ref_stats(message.chat.id)
    else:
        try:
            await message.answer("Проходка 🎟")
            await bot.send_invoice(
                chat_id=message.chat.id,
                title="Проходка",
                description="Доступ к функционалу бота",
                payload="buy_pass",
                currency="XTR",
                prices=[LabeledPrice(label="Проходка", amount=PASS_PRICE)]
            )
        except TelegramForbiddenError:
            pass # Если юзер успел заблокировать бота

# 2. Подтверждение оплаты
@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)

# 3. Успешная оплата
@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    user = get_user(message.from_user.id)
    
    if user["paid"]:
        return
        
    user["paid"] = True
    
    if user["invited_by"]:
        inviter = get_user(user["invited_by"])
        inviter["refs_paid"] += 1
        
        if inviter["refs_paid"] >= REF_GOAL and not inviter["bear_received"]:
            success = await send_gift_to_api(
                user_id=user["invited_by"], 
                gift_id=GIFT_ID, 
                text="Награда за 10 приглашенных! 🧸"
            )
            if success:
                inviter["bear_received"] = True
                try:
                    await bot.send_message(user["invited_by"], "🎉 Вы пригласили 10 человек! Вам отправлен подарок 🧸")
                except TelegramForbiddenError:
                    pass # Пригласивший заблокировал бота
            else:
                try:
                    await bot.send_message(ADMIN_ID, f"⚠️ Ошибка отправки мишки юзеру {user['invited_by']}. Недостаточно звезд?")
                except:
                    pass

    await send_ref_stats(message.chat.id)

# Функция вывода статистики
async def send_ref_stats(chat_id):
    user = get_user(chat_id)
    bot_info = await bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{chat_id}"
    
    unpaid_refs = user["refs_total"] - user["refs_paid"]
    
    text = (
        f"ref: {ref_link}\n\n"
        f"люди которые купили проходку по реферальной ссылке: {user['refs_paid']}/{REF_GOAL}\n"
        f"люди которые не купили проходку: {unpaid_refs}/{REF_GOAL}"
    )
    
    if user["bear_received"]:
        text += "\n\n✅ Вы уже получили мишку!"
    elif user["refs_paid"] >= REF_GOAL:
         text += "\n\n🎉 Вы набрали 10 покупок! Мишка скоро придет!"
        
    try:
        await bot.send_message(chat_id, text)
    except TelegramForbiddenError:
        pass # Заблокировал бота

# === АДМИН КОМАНДЫ ===

@router.message(Command("send"), F.from_user.id == ADMIN_ID)
async def admin_send(message: Message, command: CommandObject):
    text = command.args if command.args else "Подарок от админа"
    await message.answer("⏳ Пытаюсь отправить мишку на 333000...")
    success = await send_gift_to_api(user_id=TARGET_GIFT_ID, gift_id=GIFT_ID, text=text)
    if success:
        await message.answer("✅ Мишка успешно отправлена в 333000!")
    else:
        await message.answer("❌ Ошибка. У бота нет звезд или телеграм заблокировал отправку.")

@router.message(Command("check"), F.from_user.id == ADMIN_ID)
async def admin_check(message: Message, command: CommandObject):
    try:
        amount = int(command.args) if command.args else 10
        if amount < 1: amount = 1
    except:
        amount = 10

    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Пополнение баланса бота",
        description=f"Покупка {amount} Stars для бота",
        payload="top_up_stars",
        currency="XTR",
        prices=[LabeledPrice(label=f"{amount} Stars", amount=amount)]
    )

# === ЗАПУСК ===
async def main():
    dp = Dispatcher()
    dp.include_router(router)
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())