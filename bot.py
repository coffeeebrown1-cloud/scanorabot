import logging
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
 
TELEGRAM_TOKEN = "8655661569:AAHW1CQeTRSNycWyGVvVhHM9qHCkgJca8kI"
GROK_API_KEY   = "xai-Z6XeDJWoAIcIGcHZ7Idmmf2QfZV1cR7crg889898C5TVLHJjPfFurrnDkFdY267XlZXLz9H7hnaNN4Yd"
OWNER_CHAT_ID  = 356161113
 
SYSTEM_PROMPT = """Ты — Екатерина, доброжелательный ассистент компании SCANORA (Санкт-Петербург).
Ты общаешься с клиентами в Telegram от имени компании. Говори тепло, вежливо, по-русски.
Никогда не говори что ты ИИ или бот.
 
О КОМПАНИИ SCANORA:
Выездное 3D-сканирование зубов в Санкт-Петербурге.
Специалист приезжает в клинику клиента — не нужно покупать оборудование.
Оборудование: LAUNCA DL-300.
Форматы файлов: STL / PLY / OBJ — передаются в день визита.
Сайт: scanora.online
Телефон/WhatsApp: +7 (996) 755-47-03
Email: info@scanora.online
 
ЦЕНЫ:
- Обычная цена первого сканирования: 6 000 ₽
- Обычная цена последующих: 3 500 ₽ каждое
 
АКЦИЯ ДЛЯ НОВЫХ КЛИЕНТОВ (не от партнёра):
- При заказе от 2-х сканирований — первое БЕСПЛАТНО
- Итого за два: вместо 9 500 ₽ платите всего 3 500 ₽
- Выезд специалиста: бесплатно
 
КЛИЕНТЫ ОТ ПАРТНЁРА:
- Первое сканирование полностью БЕСПЛАТНО (без условий)
 
КАК РАБОТАЕТ:
1. Клиент оставляет заявку
2. Согласовываем удобное время визита
3. Специалист приезжает с оборудованием
4. Цифровые модели передаются в день визита
 
ТРИГГЕРНЫЕ СИТУАЦИИ:
Если клиент хочет ЗАПИСАТЬСЯ — напиши ТОЛЬКО эту фразу, ничего больше:
"Уточню по поводу записи, одну минуту 🙏"
 
Если клиент спрашивает про ДОСТАВКУ файлов — напиши ТОЛЬКО эту фразу, ничего больше:
"Уточню по поводу доставки, одну минуту 🙏"
 
ВАЖНО:
- Отвечай только по теме SCANORA
- Будь краткой и дружелюбной
- Если не знаешь ответа — предложи: +7 (996) 755-47-03"""
 
chat_histories = {}
paused_chats = set()
 
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
 
async def ask_grok(chat_id: int, user_message: str) -> str:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
 
    chat_histories[chat_id].append({"role": "user", "content": user_message})
    history = chat_histories[chat_id][-20:]
 
    payload = {
        "model": "grok-3-latest",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + history,
        "max_tokens": 500,
        "temperature": 0.7
    }
 
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        data = response.json()
 
    reply = data["choices"][0]["message"]["content"]
    chat_histories[chat_id].append({"role": "assistant", "content": reply})
    return reply
 
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Здравствуйте! Я Екатерина, ассистент компании SCANORA 😊\n"
        "Задайте любой вопрос о нашем 3D-сканировании зубов."
    )
 
async def reply_to_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /reply [chat_id] [текст]")
        return
 
    client_chat_id = int(context.args[0])
    message_text = " ".join(context.args[1:])
 
    try:
        await context.bot.send_message(chat_id=client_chat_id, text=message_text)
        await update.message.reply_text(f"✅ Отправлено клиенту {client_chat_id}")
        if client_chat_id not in chat_histories:
            chat_histories[client_chat_id] = []
        chat_histories[client_chat_id].append({"role": "assistant", "content": message_text})
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")
 
async def resume_client(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("Формат: /resume [chat_id]")
        return
 
    client_chat_id = int(context.args[0])
    paused_chats.discard(client_chat_id)
    await update.message.reply_text(f"▶️ Екатерина снова отвечает клиенту {client_chat_id}")
    try:
        await context.bot.send_message(
            chat_id=client_chat_id,
            text="Если у вас остались вопросы — я здесь 😊"
        )
    except:
        pass
 
async def list_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_CHAT_ID:
        return
    if not chat_histories:
        await update.message.reply_text("Активных чатов нет.")
        return
 
    text = "📋 Активные чаты:\n\n"
    for chat_id in chat_histories:
        paused = "⏸ пауза" if chat_id in paused_chats else "▶️ активен"
        msgs = len(chat_histories[chat_id])
        text += f"🆔 {chat_id} — {paused} — {msgs} сообщ.\n"
    await update.message.reply_text(text)
 
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_message = update.message.text
 
    if user.id == OWNER_CHAT_ID:
        return
 
    logger.info(f"Сообщение от {user.full_name} ({chat_id}): {user_message}")
 
    # Дублируем сообщение владельцу
    await context.bot.send_message(
        chat_id=OWNER_CHAT_ID,
        text=f"💬 {user.full_name} (@{user.username or 'нет'}) [{chat_id}]:\n{user_message}"
    )
 
    # Если чат на паузе — молчим
    if chat_id in paused_chats:
        return
 
    try:
        reply = await ask_grok(chat_id, user_message)
        await update.message.reply_text(reply)
 
        # Проверяем триггеры
        triggers = ["уточню по поводу записи", "уточню по поводу доставки"]
        triggered = any(t in reply.lower() for t in triggers)
 
        if triggered:
            # Автоматически ставим на паузу
            paused_chats.add(chat_id)
 
            trigger_type = "📅 ЗАПИСЬ" if "записи" in reply.lower() else "🚚 ДОСТАВКА"
            history = chat_histories.get(chat_id, [])
            dialog_text = ""
            for msg in history[-10:]:
                role = "👤 Клиент" if msg["role"] == "user" else "🤖 Екатерина"
                dialog_text += f"{role}: {msg['content']}\n\n"
 
            notification = (
                f"⚡️ ТРИГГЕР — {trigger_type}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"👤 {user.full_name}\n"
                f"📱 @{user.username or 'нет'}\n"
                f"🆔 {chat_id}\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"💬 Диалог:\n\n{dialog_text}"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"⏸ Бот поставлен на паузу!\n\n"
                f"Ответить клиенту:\n"
                f"/reply {chat_id} [твой текст]\n\n"
                f"Включить бота обратно:\n"
                f"/resume {chat_id}"
            )
            await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=notification)
 
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(
            "Извините, произошла небольшая ошибка. "
            "Пожалуйста, напишите нам напрямую: +7 (996) 755-47-03"
        )
 
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reply", reply_to_client))
    app.add_handler(CommandHandler("resume", resume_client))
    app.add_handler(CommandHandler("list", list_chats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Екатерина FINAL запущена ✅")
    app.run_polling(drop_pending_updates=True)
