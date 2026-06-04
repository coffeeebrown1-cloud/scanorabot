import logging
import os
import json
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters

# ─── НАСТРОЙКИ ───────────────────────────────────────────────
TELEGRAM_TOKEN = "8655661569:AAHW1CQeTRSNycWyGVvVhHM9qHCkgJca8kI"
GROK_API_KEY   = "xai-Z6XeDJWoAIcIGcHZ7Idmmf2QfZV1cR7crg889898C5TVLHJjPfFurrnDkFdY267XlZXLz9H7hnaNN4Yd"
OWNER_CHAT_ID  = 356161113   # твой Telegram ID для уведомлений

# ─── СИСТЕМНЫЙ ПРОМПТ ЕКАТЕРИНЫ ───────────────────────────────
SYSTEM_PROMPT = """Ты — Екатерина, доброжелательный ассистент компании SCANORA (Санкт-Петербург).
Ты общаешься с клиентами в Telegram от имени компании. Говори тепло, вежливо, по-русски.
Никогда не говори что ты ИИ или бот.

━━━━━━━━━━━━━━━━━━━━━━━
О КОМПАНИИ SCANORA:
━━━━━━━━━━━━━━━━━━━━━━━
Выездное 3D-сканирование зубов в Санкт-Петербурге.
Специалист приезжает в клинику клиента — не нужно покупать оборудование.
Оборудование: LAUNCA DL-300.
Форматы файлов: STL / PLY / OBJ — передаются в день визита.
Сайт: scanora.online
Телефон/WhatsApp: +7 (996) 755-47-03
Email: info@scanora.online

━━━━━━━━━━━━━━━━━━━━━━━
ЦЕНЫ:
━━━━━━━━━━━━━━━━━━━━━━━
- Обычная цена первого сканирования: 6 000 ₽
- Обычная цена последующих: 3 500 ₽ каждое

АКЦИЯ ДЛЯ НОВЫХ КЛИЕНТОВ (не от партнёра):
- При заказе от 2-х сканирований — первое БЕСПЛАТНО
- Итого за два: вместо 9 500 ₽ платите всего 3 500 ₽
- Выезд специалиста: бесплатно

КЛИЕНТЫ ОТ ПАРТНЁРА:
- Первое сканирование полностью БЕСПЛАТНО (без условий)

━━━━━━━━━━━━━━━━━━━━━━━
КАК РАБОТАЕТ:
━━━━━━━━━━━━━━━━━━━━━━━
1. Клиент оставляет заявку
2. Согласовываем удобное время визита
3. Специалист приезжает с оборудованием
4. Цифровые модели передаются в день визита

━━━━━━━━━━━━━━━━━━━━━━━
ТРИГГЕРНЫЕ СИТУАЦИИ:
━━━━━━━━━━━━━━━━━━━━━━━
Если клиент хочет ЗАПИСАТЬСЯ на сканирование — напиши ТОЧНО:
"Уточню по поводу записи, одну минуту 🙏"
И больше ничего не добавляй в этом сообщении.

Если клиент спрашивает про ДОСТАВКУ файлов или логистику — напиши ТОЧНО:
"Уточню по поводу доставки, одну минуту 🙏"
И больше ничего не добавляй в этом сообщении.

━━━━━━━━━━━━━━━━━━━━━━━
ВАЖНО:
━━━━━━━━━━━━━━━━━━━━━━━
- Отвечай только по теме SCANORA
- Будь краткой и дружелюбной
- Не выдумывай информацию которой нет выше
- Если не знаешь ответа — предложи связаться напрямую: +7 (996) 755-47-03"""

# ─── ХРАНИЛИЩЕ ИСТОРИИ ДИАЛОГОВ ──────────────────────────────
chat_histories = {}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── ЗАПРОС К GROK API ───────────────────────────────────────
async def ask_grok(chat_id: int, user_message: str) -> str:
    import httpx

    if chat_id not in chat_histories:
        chat_histories[chat_id] = []

    chat_histories[chat_id].append({"role": "user", "content": user_message})

    # Ограничиваем историю последними 20 сообщениями
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

# ─── ОБРАБОТЧИК СООБЩЕНИЙ ────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    user_message = update.message.text

    # Отвечаем клиенту
    reply = await ask_grok(chat_id, user_message)
    await update.message.reply_text(reply)

    # Проверяем триггеры
    triggers = ["уточню по поводу записи", "уточню по поводу доставки"]
    triggered = any(t in reply.lower() for t in triggers)

    if triggered:
        # Собираем историю диалога для уведомления
        history = chat_histories.get(chat_id, [])
        dialog_text = ""
        for msg in history[-10:]:
            role = "👤 Клиент" if msg["role"] == "user" else "🤖 Екатерина"
            dialog_text += f"{role}: {msg['content']}\n\n"

        trigger_type = "📅 ЗАПИСЬ" if "записи" in reply.lower() else "🚚 ДОСТАВКА"

        notification = (
            f"⚡️ ТРИГГЕР — {trigger_type}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Клиент: {user.full_name}\n"
            f"🆔 ID: {user.id}\n"
            f"📱 Username: @{user.username or 'не указан'}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"💬 Диалог:\n\n{dialog_text}"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👉 Напиши клиенту лично или передай менеджеру!"
        )

        await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=notification)

# ─── ЗАПУСК ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Екатерина запущена ✅")
    app.run_polling()
