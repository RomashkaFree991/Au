import asyncio
from telethon import TelegramClient, events, types

# --- ВАШИ ДАННЫЕ ---
API_ID = 36082409
API_HASH = '383b20ae7b4aeedaa9958e827d21979d'
# -------------------

client = TelegramClient('my_session', API_ID, API_HASH)

mailing_active = False
broadcast_message = ""

async def mailing_loop():
    global mailing_active, broadcast_message
    
    while True:
        if mailing_active and broadcast_message:
            print("--- Запуск цикла рассылки ---")
            
            # Получаем актуальный список групп
            groups = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    groups.append(dialog)

            if not groups:
                print("Группы не найдены.")
            else:
                for dialog in groups:
                    if not mailing_active:
                        break
                    try:
                        # Отправляем сообщение
                        await client.send_message(dialog.id, broadcast_message)
                        print(f"✅ Отправлено в: {dialog.name} ({dialog.id})")
                        # Небольшая пауза 0.3 сек, чтобы ТГ не выкинул за слишком частые запросы
                        await asyncio.sleep(0.3) 
                    except Exception as e:
                        print(f"❌ Ошибка в {dialog.name}: {e}")

            print("--- Круг завершен. Жду 3 минуты (180 сек) ---")
            # Ждем 3 минуты до следующего круга
            for _ in range(180):
                if not mailing_active: break
                await asyncio.sleep(1)
        else:
            await asyncio.sleep(3)

# Команда /start
@client.on(events.NewMessage(pattern='/start', outgoing=True))
async def start_handler(event):
    global mailing_active
    if not broadcast_message:
        await event.edit("❌ Ошибка: Сообщение пустое! Напишите `/sb Текст`")
        return
    mailing_active = True
    await event.edit(f"🚀 **Рассылка запущена!**\nИнтервал: каждые 3 минуты.\nТекст:\n{broadcast_message}")

# Команда /stop
@client.on(events.NewMessage(pattern='/stop', outgoing=True))
async def stop_handler(event):
    global mailing_active
    mailing_active = False
    await event.edit("🛑 **Рассылка остановлена.**")

# Команда /sb (изменить сообщение)
@client.on(events.NewMessage(pattern=r'(?s)/sb (.+)', outgoing=True))
async def set_msg_handler(event):
    global broadcast_message
    broadcast_message = event.pattern_match.group(1)
    await event.edit(f"📝 **Текст сохранен:**\n\n{broadcast_message}")

async def main():
    await client.start()
    print("Бот запущен. Управление в 'Избранном'.")
    print("Команды: /sb [текст], /start, /stop")
    
    # Запускаем рассылку фоном
    asyncio.create_task(mailing_loop())
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())