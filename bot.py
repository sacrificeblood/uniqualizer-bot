"""
Telegram Image Uniqualizer Bot
- Принимает фото как файл
- Создаёт 6 уникальных JPEG (качество 95) — лёгкие и быстрые
- Отправляет ZIP архивом
"""

import os
import io
import random
import logging
import zipfile
import time
from PIL import Image, ImageEnhance, ImageFilter

TOKEN = os.getenv("BOT_TOKEN", "8683713082:AAE196Xk0R5zL_8jPhN3iW6wdJcPMZVO9k4")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

import telebot
# Увеличиваем таймауты
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 120


# ─── МЕТОДЫ (только цвет/яркость — без поворота и флипа) ─────────────────────

def method_1(img):
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.07))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.06))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.35))
    return img

def method_2(img):
    img = ImageEnhance.Color(img).enhance(random.uniform(0.88, 1.18))
    r, g, b = img.split()
    shift_r = random.randint(-10, 10)
    shift_b = random.randint(-10, 10)
    r = r.point(lambda x: max(0, min(255, x + shift_r)))
    b = b.point(lambda x: max(0, min(255, x + shift_b)))
    return Image.merge("RGB", (r, g, b))

def method_3(img):
    gamma = random.uniform(0.88, 1.14)
    lut = [max(0, min(255, int((i / 255.0) ** gamma * 255))) for i in range(256)]
    return img.point(lut * 3)

def method_4(img):
    r, g, b = img.split()
    r = r.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    g = g.point(lambda x: max(0, min(255, x + random.randint(-8,  8))))
    b = b.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.97, 1.04))
    return img

def method_5(img):
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.5)))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(1.3, 1.8))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.97, 1.05))
    return img

def method_6(img):
    img = ImageEnhance.Color(img).enhance(random.uniform(0.90, 1.15))
    gamma = random.uniform(0.91, 1.10)
    lut = [max(0, min(255, int((i / 255.0) ** gamma * 255))) for i in range(256)]
    img = img.point(lut * 3)
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.07))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.96, 1.05))
    return img


METHODS = [
    ("variant_1_brightness", method_1),
    ("variant_2_colorshift",  method_2),
    ("variant_3_gamma",       method_3),
    ("variant_4_rgb",         method_4),
    ("variant_5_sharpen",     method_5),
    ("variant_6_combo",       method_6),
]


def uniqualize_to_zip(image_bytes: bytes, original_filename: str = "image") -> bytes:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    base_name = os.path.splitext(original_filename)[0]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for method_name, method_fn in METHODS:
            try:
                processed = method_fn(original.copy())
                img_buf = io.BytesIO()
                # JPEG качество 95 — отличное качество, небольшой размер
                processed.save(img_buf, format="JPEG", quality=95, subsampling=0)
                img_buf.seek(0)
                zf.writestr(f"{base_name}_{method_name}.jpg", img_buf.read())
                log.info(f"OK: {method_name}")
            except Exception as e:
                log.error(f"Ошибка {method_name}: {e}")
                img_buf = io.BytesIO()
                original.save(img_buf, format="JPEG", quality=95, subsampling=0)
                img_buf.seek(0)
                zf.writestr(f"{base_name}_{method_name}.jpg", img_buf.read())

    zip_buf.seek(0)
    return zip_buf.read()


def send_with_retry(func, *args, retries=3, delay=5, **kwargs):
    """Отправка с повторными попытками при таймауте"""
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.warning(f"Попытка {attempt}/{retries} провалилась: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise


def process_and_send(chat_id, image_bytes, filename, status_msg_id):
    try:
        bot.edit_message_text("⚙️ Создаю 6 уникальных версий...", chat_id, status_msg_id)
        zip_bytes = uniqualize_to_zip(image_bytes, filename)
        size_kb = len(zip_bytes) / 1024
        log.info(f"ZIP размер: {size_kb:.1f} KB")

        bot.edit_message_text(f"📦 Отправляю ZIP ({size_kb:.0f} KB)...", chat_id, status_msg_id)

        zip_name = os.path.splitext(filename)[0] + "_uniqualized.zip"

        send_with_retry(
            bot.send_document,
            chat_id,
            document=(zip_name, io.BytesIO(zip_bytes)),
            caption=(
                "✅ <b>6 уникальных версий готовы!</b>\n"
                "📂 JPEG 95% — высокое качество\n"
                "🔁 Пришли следующее фото!"
            )
        )

        bot.delete_message(chat_id, status_msg_id)

    except Exception as e:
        log.error(f"Ошибка: {e}")
        try:
            bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg_id)
        except Exception:
            bot.send_message(chat_id, f"❌ Ошибка: <code>{e}</code>")


# ─── HANDLERS ────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Image Uniqualizer Bot</b>\n\n"
        "📎 Отправь фото <b>как файл</b> (скрепка → Файл) — лучшее качество\n"
        "📸 Или просто фото — тоже работает\n\n"
        "Получишь <b>ZIP с 6 уникальными JPEG</b> (качество 95%).\n\n"
        "Методы:\n"
        "• Яркость / контраст / резкость\n"
        "• Цветовой сдвиг\n"
        "• Гамма-коррекция\n"
        "• RGB микс\n"
        "• Размытие + резкость\n"
        "• Комбо\n\n"
        "⚡ Без поворотов и зеркал!"
    )


@bot.message_handler(content_types=["document"])
def handle_document(message):
    chat_id = message.chat.id
    doc = message.document

    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        bot.send_message(chat_id, "⚠️ Это не изображение!")
        return

    status_msg = bot.send_message(chat_id, "⏳ Скачиваю файл...")
    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        process_and_send(chat_id, downloaded, doc.file_name or "image.jpg", status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка скачивания: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    chat_id = message.chat.id
    status_msg = bot.send_message(
        chat_id,
        "⏳ Скачиваю...\n"
        "<i>💡 Для лучшего качества отправляй как файл (скрепка → Файл)</i>"
    )
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        process_and_send(chat_id, downloaded, "photo.jpg", status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка скачивания: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    bot.send_message(
        message.chat.id,
        "📎 Пришли фото как файл или просто фотографию!\n/help — инструкция"
    )


if __name__ == "__main__":
    log.info("Бот запущен...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
