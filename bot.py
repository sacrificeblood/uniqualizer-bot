"""
Telegram Image Uniqualizer Bot
- Размер выхода: 720x1280 (TikTok/Reels)
- Фон определяется по краям оригинала (точнее)
- Градиент из реального цвета фона
- 6 уникальных JPEG 95% в ZIP
"""

import os
import io
import random
import logging
import zipfile
import time
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

TOKEN = os.getenv("BOT_TOKEN", "8683713082:AAE196Xk0R5zL_8jPhN3iW6wdJcPMZVO9k4")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

import telebot
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 120

OUTPUT_W = 720
OUTPUT_H = 1280


# ─── ТОЧНОЕ ОПРЕДЕЛЕНИЕ ЦВЕТА ФОНА ───────────────────────────────────────────

def get_edge_color(img: Image.Image) -> tuple:
    """
    Берёт пиксели только с краёв изображения (5% полоса по периметру).
    Это даёт реальный цвет фона, а не объектов в центре.
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    border = max(1, int(min(w, h) * 0.05))

    pixels = []
    # Верхняя полоса
    for x in range(w):
        for y in range(border):
            pixels.append(rgb.getpixel((x, y)))
    # Нижняя полоса
    for x in range(w):
        for y in range(h - border, h):
            pixels.append(rgb.getpixel((x, y)))
    # Левая полоса
    for x in range(border):
        for y in range(border, h - border):
            pixels.append(rgb.getpixel((x, y)))
    # Правая полоса
    for x in range(w - border, w):
        for y in range(border, h - border):
            pixels.append(rgb.getpixel((x, y)))

    if not pixels:
        return (30, 30, 30)

    r = int(sum(p[0] for p in pixels) / len(pixels))
    g = int(sum(p[1] for p in pixels) / len(pixels))
    b = int(sum(p[2] for p in pixels) / len(pixels))

    log.info(f"Цвет края: RGB({r},{g},{b})")
    return (r, g, b)


def scale_color(color: tuple, factor: float) -> tuple:
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def make_gradient_bg(size: tuple, color: tuple) -> Image.Image:
    """
    Вертикальный градиент:
    сверху — тёмная версия цвета
    середина — чуть светлее
    снизу — снова тёмнее
    """
    w, h = size
    bg = Image.new("RGB", size)
    draw = ImageDraw.Draw(bg)

    top    = scale_color(color, 0.40)
    mid    = scale_color(color, 0.70)
    bottom = scale_color(color, 0.30)

    for y in range(h):
        t = y / (h - 1)
        if t < 0.45:
            ratio = t / 0.45
            r = int(top[0] + (mid[0] - top[0]) * ratio)
            g = int(top[1] + (mid[1] - top[1]) * ratio)
            b = int(top[2] + (mid[2] - top[2]) * ratio)
        else:
            ratio = (t - 0.45) / 0.55
            r = int(mid[0] + (bottom[0] - mid[0]) * ratio)
            g = int(mid[1] + (bottom[1] - mid[1]) * ratio)
            b = int(mid[2] + (bottom[2] - mid[2]) * ratio)
        draw.line([(0, y), (w - 1, y)], fill=(r, g, b))

    return bg


def place_on_canvas(img: Image.Image) -> Image.Image:
    """
    1. Определяет цвет фона по краям
    2. Создаёт канвас 720x1280 с градиентом
    3. Вписывает оригинал по центру с отступами ~10%
    """
    edge_color = get_edge_color(img)
    bg = make_gradient_bg((OUTPUT_W, OUTPUT_H), edge_color)

    # Зона для изображения: 80% ширины и высоты канваса
    max_w = int(OUTPUT_W * 0.82)
    max_h = int(OUTPUT_H * 0.82)

    # Масштабируем оригинал вписываясь в max_w x max_h
    img_copy = img.copy()
    img_copy.thumbnail((max_w, max_h), Image.LANCZOS)

    # Центрируем
    paste_x = (OUTPUT_W - img_copy.width) // 2
    paste_y = (OUTPUT_H - img_copy.height) // 2

    bg.paste(img_copy, (paste_x, paste_y))
    return bg


# ─── МЕТОДЫ УНИКАЛИЗАЦИИ ─────────────────────────────────────────────────────

def method_1(img):
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.07))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.06))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.35))
    return img

def method_2(img):
    img = ImageEnhance.Color(img).enhance(random.uniform(0.88, 1.18))
    r, g, b = img.split()
    sr = random.randint(-10, 10)
    sb = random.randint(-10, 10)
    r = r.point(lambda x: max(0, min(255, x + sr)))
    b = b.point(lambda x: max(0, min(255, x + sb)))
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
    ("v1_brightness", method_1),
    ("v2_colorshift",  method_2),
    ("v3_gamma",       method_3),
    ("v4_rgb",         method_4),
    ("v5_sharpen",     method_5),
    ("v6_combo",       method_6),
]


def uniqualize_to_zip(image_bytes: bytes, original_filename: str = "image") -> bytes:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    base_name = os.path.splitext(original_filename)[0]

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for method_name, method_fn in METHODS:
            try:
                processed = method_fn(original.copy())
                canvas = place_on_canvas(processed)
                img_buf = io.BytesIO()
                canvas.save(img_buf, format="JPEG", quality=95, subsampling=0)
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
    for attempt in range(1, retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.warning(f"Попытка {attempt}/{retries}: {e}")
            if attempt < retries:
                time.sleep(delay)
            else:
                raise


def process_and_send(chat_id, image_bytes, filename, status_msg_id):
    try:
        bot.edit_message_text("🎨 Анализирую цвет фона...", chat_id, status_msg_id)
        zip_bytes = uniqualize_to_zip(image_bytes, filename)
        size_kb = len(zip_bytes) / 1024
        bot.edit_message_text(f"📦 Отправляю ZIP ({size_kb:.0f} KB)...", chat_id, status_msg_id)
        zip_name = os.path.splitext(filename)[0] + "_uniqualized.zip"
        send_with_retry(
            bot.send_document,
            chat_id,
            document=(zip_name, io.BytesIO(zip_bytes)),
            caption=(
                "✅ <b>6 уникальных версий готовы!</b>\n"
                "📐 Размер: 720×1280\n"
                "🎨 Градиент подобран по краям креатива\n"
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
        "📎 Отправь фото <b>как файл</b> (скрепка → Файл)\n"
        "📸 Или просто фото\n\n"
        "Что делает:\n"
        "📐 Размер выхода: <b>720×1280</b>\n"
        "🎨 Анализирует цвет по краям → градиент\n"
        "✨ 6 уникальных версий в ZIP\n\n"
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
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    chat_id = message.chat.id
    status_msg = bot.send_message(
        chat_id,
        "⏳ Скачиваю...\n"
        "<i>💡 Для лучшего качества — отправляй как файл (скрепка → Файл)</i>"
    )
    try:
        file_id = message.photo[-1].file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)
        process_and_send(chat_id, downloaded, "photo.jpg", status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    bot.send_message(
        message.chat.id,
        "📎 Пришли фото как файл или просто фотографию!\n/help — инструкция"
    )


if __name__ == "__main__":
    log.info("Бот запущен...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
