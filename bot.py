"""
Telegram Image Uniqualizer Bot
- Принимает фото (как файл для максимального качества)
- Создаёт 6 уникальных версий БЕЗ поворота/флипа
- Сохраняет PNG без потерь
- Отправляет одним ZIP архивом
"""

import os
import io
import random
import logging
import zipfile
from PIL import Image, ImageEnhance, ImageFilter

TOKEN = os.getenv("BOT_TOKEN", "8683713082:AAE196Xk0R5zL_8jPhN3iW6wdJcPMZVO9k4")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

import telebot
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ─── МЕТОДЫ (только цвет/яркость/резкость — без поворота и флипа) ────────────

def method_1(img: Image.Image) -> Image.Image:
    """Яркость + контраст + резкость"""
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.07))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.06))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.35))
    return img

def method_2(img: Image.Image) -> Image.Image:
    """Насыщенность + тёплый/холодный оттенок"""
    img = ImageEnhance.Color(img).enhance(random.uniform(0.88, 1.18))
    r, g, b = img.split()
    shift_r = random.randint(-10, 10)
    shift_b = random.randint(-10, 10)
    r = r.point(lambda x: max(0, min(255, x + shift_r)))
    b = b.point(lambda x: max(0, min(255, x + shift_b)))
    return Image.merge("RGB", (r, g, b))

def method_3(img: Image.Image) -> Image.Image:
    """Гамма-коррекция через point"""
    gamma = random.uniform(0.88, 1.14)
    lut = [max(0, min(255, int((i / 255.0) ** gamma * 255))) for i in range(256)]
    lut3 = lut * 3
    return img.point(lut3)

def method_4(img: Image.Image) -> Image.Image:
    """Микро-сдвиг RGB каналов независимо"""
    r, g, b = img.split()
    r = r.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    g = g.point(lambda x: max(0, min(255, x + random.randint(-8, 8))))
    b = b.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    img = Image.merge("RGB", (r, g, b))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.97, 1.04))
    return img

def method_5(img: Image.Image) -> Image.Image:
    """Лёгкое размытие + усиление резкости"""
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.6)))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(1.3, 1.8))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.97, 1.05))
    return img

def method_6(img: Image.Image) -> Image.Image:
    """Комбо: насыщенность + гамма + контраст"""
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
    ("variant_4_rgb_mix",     method_4),
    ("variant_5_sharpen",     method_5),
    ("variant_6_combo",       method_6),
]


def uniqualize_to_zip(image_bytes: bytes, original_filename: str = "image") -> bytes:
    """
    Принимает байты изображения.
    Возвращает байты ZIP с 6 PNG файлами.
    """
    # Определяем формат оригинала
    original = Image.open(io.BytesIO(image_bytes))

    # Сохраняем EXIF если есть
    exif_data = None
    try:
        exif_data = original.info.get("exif")
    except Exception:
        pass

    original = original.convert("RGB")

    # Имя без расширения
    base_name = os.path.splitext(original_filename)[0]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for method_name, method_fn in METHODS:
            try:
                processed = method_fn(original.copy())
                img_buf = io.BytesIO()
                # PNG — без потерь, сохраняем максимальное качество
                save_kwargs = {"format": "PNG", "optimize": False, "compress_level": 1}
                processed.save(img_buf, **save_kwargs)
                img_buf.seek(0)
                filename = f"{base_name}_{method_name}.png"
                zf.writestr(filename, img_buf.read())
                log.info(f"Обработан метод: {method_name}")
            except Exception as e:
                log.error(f"Ошибка метода {method_name}: {e}")
                # fallback — оригинал
                img_buf = io.BytesIO()
                original.save(img_buf, format="PNG", compress_level=1)
                img_buf.seek(0)
                zf.writestr(f"{base_name}_{method_name}_original.png", img_buf.read())

    zip_buf.seek(0)
    return zip_buf.read()


# ─── HANDLERS ────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Image Uniqualizer Bot</b>\n\n"
        "📎 Отправь фото <b>как файл</b> (скрепка → Файл) для максимального качества\n"
        "📸 Или просто фото — тоже работает\n\n"
        "Получишь <b>ZIP архив с 6 уникальными PNG</b> без потери качества.\n\n"
        "Методы уникализации:\n"
        "• Яркость / контраст / резкость\n"
        "• Цветовой сдвиг (тёплый/холодный)\n"
        "• Гамма-коррекция\n"
        "• Независимый сдвиг RGB каналов\n"
        "• Размытие + усиление резкости\n"
        "• Комбо-обработка\n\n"
        "⚡ Без поворотов и зеркального отражения!"
    )


def process_and_send(chat_id: int, image_bytes: bytes, filename: str, status_msg_id: int):
    """Общая логика обработки и отправки ZIP"""
    try:
        bot.edit_message_text("⚙️ Создаю 6 уникальных версий...", chat_id, status_msg_id)

        zip_bytes = uniqualize_to_zip(image_bytes, filename)

        bot.edit_message_text("📦 Упаковываю в ZIP...", chat_id, status_msg_id)

        zip_name = os.path.splitext(filename)[0] + "_uniqualized.zip"

        bot.delete_message(chat_id, status_msg_id)
        bot.send_document(
            chat_id,
            document=(zip_name, io.BytesIO(zip_bytes)),
            caption=(
                "✅ <b>6 уникальных версий готовы!</b>\n"
                "📂 PNG файлы без потери качества\n"
                "🔁 Пришли следующее фото!"
            )
        )

    except Exception as e:
        log.error(f"Ошибка обработки: {e}")
        try:
            bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg_id)
        except Exception:
            bot.send_message(chat_id, f"❌ Ошибка: <code>{e}</code>")


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """Фото как файл — максимальное качество"""
    chat_id = message.chat.id
    doc = message.document

    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        bot.send_message(chat_id, "⚠️ Это не изображение. Пришли фото или файл изображения!")
        return

    status_msg = bot.send_message(chat_id, "⏳ Скачиваю файл...")

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)
        filename = doc.file_name or "image.jpg"
        process_and_send(chat_id, downloaded, filename, status_msg.message_id)
    except Exception as e:
        log.error(f"Ошибка скачивания: {e}")
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """Обычное фото (сжатое Telegram'ом)"""
    chat_id = message.chat.id
    status_msg = bot.send_message(
        chat_id,
        "⏳ Скачиваю...\n"
        "<i>💡 Совет: отправляй как файл (скрепка → Файл) для лучшего качества</i>"
    )

    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        process_and_send(chat_id, downloaded, "photo.jpg", status_msg.message_id)
    except Exception as e:
        log.error(f"Ошибка скачивания фото: {e}")
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    bot.send_message(
        message.chat.id,
        "📎 Пришли фото <b>как файл</b> или просто фотографию!\n"
        "/help — инструкция"
    )


# ─── RUN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Бот запущен...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
