"""
Telegram Image Uniqualizer Bot
Принимает фото → создаёт 6 уникальных версий → отправляет обратно
"""

import os
import io
import random
import logging
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import telebot
from telebot.types import InputMediaPhoto

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "8683713082:AAE196Xk0R5zL_8jPhN3iW6wdJcPMZVO9k4")
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")


# ─── UNIQUALIZATION METHODS ───────────────────────────────────────────────────

def method_1_brightness_contrast(img: Image.Image) -> Image.Image:
    """Яркость + контраст + лёгкий шарп"""
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.93, 1.08))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.06))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.9, 1.3))
    return img


def method_2_color_shift(img: Image.Image) -> Image.Image:
    """Сдвиг насыщенности и цветового баланса"""
    img = ImageEnhance.Color(img).enhance(random.uniform(0.88, 1.15))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.96, 1.05))
    # лёгкий теплый/холодный сдвиг через RGB
    r, g, b = img.split()
    r = r.point(lambda x: min(255, x + random.randint(-8, 8)))
    b = b.point(lambda x: min(255, x + random.randint(-8, 8)))
    return Image.merge("RGB", (r, g, b))


def method_3_slight_rotate(img: Image.Image) -> Image.Image:
    """Лёгкий поворот + кроп + ресайз обратно"""
    original_size = img.size
    angle = random.uniform(-1.5, 1.5)
    img = img.rotate(angle, resample=Image.BICUBIC, expand=False)
    # кроп 1-2% краёв чтобы убрать артефакты
    crop_pct = random.uniform(0.01, 0.02)
    w, h = img.size
    crop = int(min(w, h) * crop_pct)
    img = img.crop((crop, crop, w - crop, h - crop))
    img = img.resize(original_size, Image.LANCZOS)
    return img


def method_4_flip_mirror(img: Image.Image) -> Image.Image:
    """Горизонтальный флип + цветокоррекция"""
    img = ImageOps.mirror(img)
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.97, 1.04))
    img = ImageEnhance.Color(img).enhance(random.uniform(0.95, 1.08))
    return img


def method_5_noise_blur(img: Image.Image) -> Image.Image:
    """Лёгкий шум + микро-размытие"""
    # Очень лёгкое размытие
    if random.random() > 0.5:
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 0.7)))
    else:
        img = img.filter(ImageFilter.SMOOTH)
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(1.0, 1.4))
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.97, 1.04))
    return img


def method_6_crop_resize(img: Image.Image) -> Image.Image:
    """Небольшой кроп + ресайз + цвет"""
    original_size = img.size
    w, h = img.size
    # кроп 1–3% с разных сторон неравномерно
    left   = int(w * random.uniform(0.005, 0.02))
    right  = int(w * random.uniform(0.005, 0.02))
    top    = int(h * random.uniform(0.005, 0.02))
    bottom = int(h * random.uniform(0.005, 0.02))
    img = img.crop((left, top, w - right, h - bottom))
    img = img.resize(original_size, Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(random.uniform(0.92, 1.10))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.96, 1.05))
    return img


METHODS = [
    ("🔆 Яркость/контраст",     method_1_brightness_contrast),
    ("🎨 Цветовой сдвиг",        method_2_color_shift),
    ("🔄 Поворот + кроп",        method_3_slight_rotate),
    ("🪞 Зеркало + цвет",        method_4_flip_mirror),
    ("✨ Шум + шарп",             method_5_noise_blur),
    ("✂️ Кроп + ресайз",         method_6_crop_resize),
]


def uniqualize_image(image_bytes: bytes) -> list[tuple[str, bytes]]:
    """
    Принимает исходные байты изображения.
    Возвращает список из 6 (название_метода, байты_png).
    """
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    results = []

    for name, method in METHODS:
        try:
            processed = method(original.copy())
            buf = io.BytesIO()
            processed.save(buf, format="JPEG", quality=random.randint(88, 95))
            buf.seek(0)
            results.append((name, buf.read()))
        except Exception as e:
            log.error(f"Ошибка метода '{name}': {e}")
            # fallback — отправляем оригинал
            buf = io.BytesIO()
            original.save(buf, format="JPEG", quality=90)
            buf.seek(0)
            results.append((name + " (fallback)", buf.read()))

    return results


# ─── HANDLERS ────────────────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Image Uniqualizer Bot</b>\n\n"
        "📸 Отправь мне любое фото — я создам <b>6 уникальных версий</b>!\n\n"
        "Каждая версия обрабатывается своим методом:\n"
        "• Яркость и контраст\n"
        "• Цветовой сдвиг\n"
        "• Лёгкий поворот + кроп\n"
        "• Зеркало + цветокоррекция\n"
        "• Шум + резкость\n"
        "• Кроп + ресайз\n\n"
        "🔁 Каждый раз результат будет немного другим!\n\n"
        "Просто пришли фото ⬇️"
    )


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    chat_id = message.chat.id

    # Статус
    status_msg = bot.send_message(chat_id, "⏳ Обрабатываю фото...")

    try:
        # Скачиваем файл (берём наибольшее фото)
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        # Уникализируем
        results = uniqualize_image(downloaded)

        # Удаляем статус
        bot.delete_message(chat_id, status_msg.message_id)

        # Отправляем альбомом (группой)
        media_group = []
        for i, (name, img_bytes) in enumerate(results):
            caption = f"<b>#{i+1}</b> — {name}" if i == 0 else f"#{i+1} — {name}"
            media_group.append(
                InputMediaPhoto(
                    media=img_bytes,
                    caption=caption,
                    parse_mode="HTML"
                )
            )

        bot.send_media_group(chat_id, media_group)

        bot.send_message(
            chat_id,
            "✅ Готово! <b>6 уникальных версий</b> отправлены.\n"
            "📤 Можешь прислать следующее фото!",
        )

    except Exception as e:
        log.error(f"Ошибка обработки фото: {e}")
        bot.edit_message_text(
            f"❌ Ошибка: <code>{e}</code>",
            chat_id,
            status_msg.message_id
        )


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """Если отправили фото как файл (без сжатия)"""
    chat_id = message.chat.id
    doc = message.document

    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        bot.send_message(chat_id, "⚠️ Это не изображение. Пришли фото!")
        return

    status_msg = bot.send_message(chat_id, "⏳ Обрабатываю изображение...")

    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)

        results = uniqualize_image(downloaded)

        bot.delete_message(chat_id, status_msg.message_id)

        media_group = []
        for i, (name, img_bytes) in enumerate(results):
            caption = f"<b>#{i+1}</b> — {name}" if i == 0 else f"#{i+1} — {name}"
            media_group.append(
                InputMediaPhoto(
                    media=img_bytes,
                    caption=caption,
                    parse_mode="HTML"
                )
            )

        bot.send_media_group(chat_id, media_group)
        bot.send_message(chat_id, "✅ Готово! Отправил 6 уникальных версий.")

    except Exception as e:
        log.error(f"Ошибка обработки документа: {e}")
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    bot.send_message(
        message.chat.id,
        "📸 Пришли мне фото, и я уникализирую его в 6 вариантах!\n"
        "Команда /help — инструкция."
    )


# ─── RUN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Бот запущен...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20)
