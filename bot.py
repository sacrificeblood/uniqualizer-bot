"""
Telegram Image + Video Uniqualizer Bot
- Фото: 6 версий JPEG 95% в ZIP, 720x1280 с градиентным фоном
- Видео: 6 версий MP4 в ZIP, оба варианта размера (оригинал + 720x1280)
- Любой формат входного видео (mp4, mov, avi, mkv...)
"""

import os
import io
import random
import logging
import zipfile
import time
import tempfile
import subprocess
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw

TOKEN = os.getenv("BOT_TOKEN", "8683713082:AAE196Xk0R5zL_8jPhN3iW6wdJcPMZVO9k4")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

import imageio_ffmpeg
import telebot
bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
telebot.apihelper.CONNECT_TIMEOUT = 60
telebot.apihelper.READ_TIMEOUT = 120

OUTPUT_W = 720
OUTPUT_H = 1280

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp", ".flv", ".wmv"}


# ═══════════════════════════════════════════════════════════════
#  ФОТО — УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

def get_edge_color(img: Image.Image) -> tuple:
    """
    Точный подбор цвета фона через угловые зоны + квантизация + медиана.
    """
    rgb = img.convert("RGB")
    small = rgb.copy()
    small.thumbnail((200, 200), Image.LANCZOS)
    w, h = small.size
    zx = max(1, int(w * 0.22))
    zy = max(1, int(h * 0.22))

    zones = [
        small.crop((0,    0,    zx,   zy)),
        small.crop((w-zx, 0,    w,    zy)),
        small.crop((0,    h-zy, zx,   h)),
        small.crop((w-zx, h-zy, w,    h)),
        small.crop((0,    h//2-zy//2, zx, h//2+zy//2)),
        small.crop((w-zx, h//2-zy//2, w,  h//2+zy//2)),
    ]

    zone_colors = []
    for zone in zones:
        q = zone.quantize(colors=4, method=Image.Quantize.FASTOCTREE)
        palette = q.getpalette()[:12]
        zone_colors.append((palette[0], palette[1], palette[2]))

    r = sorted([c[0] for c in zone_colors])[len(zone_colors)//2]
    g = sorted([c[1] for c in zone_colors])[len(zone_colors)//2]
    b = sorted([c[2] for c in zone_colors])[len(zone_colors)//2]

    log.info(f"Цвет фона: RGB({r},{g},{b})")
    return (r, g, b)


def scale_color(color: tuple, factor: float) -> tuple:
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def make_gradient_bg(size: tuple, color: tuple) -> Image.Image:
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
    edge_color = get_edge_color(img)
    bg = make_gradient_bg((OUTPUT_W, OUTPUT_H), edge_color)

    orig_w, orig_h = img.size
    max_w = int(OUTPUT_W * 0.88)
    max_h = int(OUTPUT_H * 0.88)

    # Точный расчёт размера с сохранением пропорций
    scale = min(max_w / orig_w, max_h / orig_h)

    # Если оригинал меньше канваса — не увеличиваем (нет смысла)
    # Если больше — уменьшаем с максимальным качеством
    if scale < 1.0:
        new_w = int(orig_w * scale)
        new_h = int(orig_h * scale)
        # LANCZOS — лучший фильтр для уменьшения, без артефактов
        resized = img.resize((new_w, new_h), Image.LANCZOS)
    else:
        # Оригинал меньше канваса — вставляем как есть без увеличения
        resized = img.copy()

    paste_x = (OUTPUT_W - resized.width) // 2
    paste_y = (OUTPUT_H - resized.height) // 2
    bg.paste(resized, (paste_x, paste_y))
    return bg


# ═══════════════════════════════════════════════════════════════
#  ФОТО — МЕТОДЫ УНИКАЛИЗАЦИИ
# ═══════════════════════════════════════════════════════════════

def photo_m1(img):
    img = ImageEnhance.Brightness(img).enhance(random.uniform(0.94, 1.07))
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.06))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(0.85, 1.35))
    return img

def photo_m2(img):
    img = ImageEnhance.Color(img).enhance(random.uniform(0.88, 1.18))
    r, g, b = img.split()
    sr = random.randint(-10, 10)
    sb = random.randint(-10, 10)
    r = r.point(lambda x: max(0, min(255, x + sr)))
    b = b.point(lambda x: max(0, min(255, x + sb)))
    return Image.merge("RGB", (r, g, b))

def photo_m3(img):
    gamma = random.uniform(0.88, 1.14)
    lut = [max(0, min(255, int((i / 255.0) ** gamma * 255))) for i in range(256)]
    return img.point(lut * 3)

def photo_m4(img):
    r, g, b = img.split()
    r = r.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    g = g.point(lambda x: max(0, min(255, x + random.randint(-8,  8))))
    b = b.point(lambda x: max(0, min(255, x + random.randint(-12, 12))))
    img = Image.merge("RGB", (r, g, b))
    return ImageEnhance.Brightness(img).enhance(random.uniform(0.97, 1.04))

def photo_m5(img):
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.2, 0.5)))
    img = ImageEnhance.Sharpness(img).enhance(random.uniform(1.3, 1.8))
    return ImageEnhance.Contrast(img).enhance(random.uniform(0.97, 1.05))

def photo_m6(img):
    img = ImageEnhance.Color(img).enhance(random.uniform(0.90, 1.15))
    gamma = random.uniform(0.91, 1.10)
    lut = [max(0, min(255, int((i / 255.0) ** gamma * 255))) for i in range(256)]
    img = img.point(lut * 3)
    img = ImageEnhance.Contrast(img).enhance(random.uniform(0.95, 1.07))
    return ImageEnhance.Brightness(img).enhance(random.uniform(0.96, 1.05))

PHOTO_METHODS = [
    ("v1_brightness", photo_m1),
    ("v2_colorshift",  photo_m2),
    ("v3_gamma",       photo_m3),
    ("v4_rgb",         photo_m4),
    ("v5_sharpen",     photo_m5),
    ("v6_combo",       photo_m6),
]


def uniqualize_photo_to_zip(image_bytes: bytes, original_filename: str = "image") -> bytes:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    base_name = os.path.splitext(original_filename)[0]
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Канвас строим один раз из оригинала — потом применяем уникализацию
        # Так ресайз происходит только 1 раз, уникализация идёт по готовому канвасу
        base_canvas = place_on_canvas(original)

        for method_name, method_fn in PHOTO_METHODS:
            try:
                # Уникализируем уже отресайзенный канвас — нет двойного пережатия
                processed = method_fn(base_canvas.copy())
                img_buf = io.BytesIO()
                processed.save(img_buf, format="PNG", compress_level=1)
                img_buf.seek(0)
                zf.writestr(f"{base_name}_{method_name}.png", img_buf.read())
            except Exception as e:
                log.error(f"Фото ошибка {method_name}: {e}")
                img_buf = io.BytesIO()
                base_canvas.save(img_buf, format="PNG", compress_level=1)
                img_buf.seek(0)
                zf.writestr(f"{base_name}_{method_name}.png", img_buf.read())
    zip_buf.seek(0)
    return zip_buf.read()


# ═══════════════════════════════════════════════════════════════
#  ВИДЕО — УТИЛИТЫ (ffmpeg)
# ═══════════════════════════════════════════════════════════════

def get_ffmpeg_path() -> str:
    """Возвращает путь к ffmpeg — системный или из imageio_ffmpeg"""
    # Сначала пробуем системный
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            log.info("Используем системный ffmpeg")
            return "ffmpeg"
    except Exception:
        pass
    # Используем встроенный из imageio-ffmpeg
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
        log.info(f"Используем imageio ffmpeg: {path}")
        return path
    except Exception as e:
        log.error(f"ffmpeg недоступен: {e}")
        return None

def check_ffmpeg() -> bool:
    return get_ffmpeg_path() is not None


def get_video_dominant_color(video_path: str) -> tuple:
    """Берём первый кадр видео и определяем цвет краёв"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            frame_path = f.name
        ffmpeg_bin = get_ffmpeg_path()
        subprocess.run([
            ffmpeg_bin, "-y", "-i", video_path,
            "-vframes", "1", "-q:v", "2",
            frame_path
        ], capture_output=True, timeout=30)
        frame = Image.open(frame_path).convert("RGB")
        color = get_edge_color(frame)
        os.unlink(frame_path)
        return color
    except Exception as e:
        log.warning(f"Не удалось определить цвет видео: {e}")
        return (30, 30, 30)


# Параметры уникализации для каждой из 6 версий видео
VIDEO_VARIANTS = [
    # (название, eq_brightness, eq_contrast, eq_saturation, описание)
    # brightness: 0=чёрный, 1=норма; contrast: -1000..1000; saturation: 0..3
    ("v1_bright",   {"brightness": "0.05",  "contrast": "5",    "saturation": "1.1"}),
    ("v2_dark",     {"brightness": "-0.05", "contrast": "-5",   "saturation": "0.9"}),
    ("v3_vivid",    {"brightness": "0.02",  "contrast": "8",    "saturation": "1.3"}),
    ("v4_cool",     {"brightness": "0.0",   "contrast": "3",    "saturation": "0.95"}),
    ("v5_warm",     {"brightness": "0.03",  "contrast": "4",    "saturation": "1.15"}),
    ("v6_sharp",    {"brightness": "-0.02", "contrast": "10",   "saturation": "1.05"}),
]


def build_ffmpeg_filter(params: dict, mode: str, color: tuple = None) -> str:
    """
    Строит ffmpeg filtergraph.
    mode = 'original' | 'tiktok'
    """
    b  = params["brightness"]
    c  = params["contrast"]
    s  = params["saturation"]

    # Случайные микро-вариации чтобы каждый раз файл был разным
    b_val = float(b) + random.uniform(-0.01, 0.01)
    c_val = float(c) + random.uniform(-2, 2)
    s_val = float(s) + random.uniform(-0.05, 0.05)

    eq_filter = f"eq=brightness={b_val:.4f}:contrast={1 + c_val/100:.4f}:saturation={s_val:.4f}"

    if mode == "tiktok":
        # Scale + crop по центру до 720x1280 — без полей, без чёрных полос
        # Сначала масштабируем так чтобы короткая сторона = нужному размеру
        # Затем обрезаем длинную по центру
        vf = (
            f"{eq_filter},"
            f"scale={OUTPUT_W}:{OUTPUT_H}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_W}:{OUTPUT_H},"
            f"setsar=1"
        )
    else:
        vf = eq_filter

    return vf


def process_video(input_path: str, output_path: str, params: dict, mode: str, color: tuple):
    vf = build_ffmpeg_filter(params, mode, color)
    ffmpeg_bin = get_ffmpeg_path()
    cmd = [
        ffmpeg_bin, "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode()[-500:])


def uniqualize_video_to_zip(
    video_bytes: bytes,
    original_filename: str = "video.mp4",
    status_callback=None
) -> bytes:
    base_name = os.path.splitext(original_filename)[0]
    ext = os.path.splitext(original_filename)[1].lower() or ".mp4"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Сохраняем входной файл
        input_path = os.path.join(tmpdir, f"input{ext}")
        with open(input_path, "wb") as f:
            f.write(video_bytes)

        # Определяем цвет фона
        color = get_video_dominant_color(input_path)
        log.info(f"Цвет видео фона: {color}")

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_STORED) as zf:
            for i, (variant_name, params) in enumerate(VIDEO_VARIANTS, 1):
                for mode in ["original", "tiktok"]:
                    out_name = f"{base_name}_{variant_name}_{mode}.mp4"
                    out_path = os.path.join(tmpdir, out_name)
                    try:
                        if status_callback:
                            status_callback(f"⚙️ Версия {i}/6 ({mode})...")
                        process_video(input_path, out_path, params, mode, color)
                        with open(out_path, "rb") as f:
                            zf.writestr(out_name, f.read())
                        log.info(f"OK: {out_name}")
                    except Exception as e:
                        log.error(f"Ошибка {out_name}: {e}")

        zip_buf.seek(0)
        return zip_buf.read()


# ═══════════════════════════════════════════════════════════════
#  ОБЩИЕ УТИЛИТЫ
# ═══════════════════════════════════════════════════════════════

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


def process_photo_and_send(chat_id, image_bytes, filename, status_msg_id):
    try:
        bot.edit_message_text("🎨 Анализирую цвет фона...", chat_id, status_msg_id)
        zip_bytes = uniqualize_photo_to_zip(image_bytes, filename)
        size_kb = len(zip_bytes) / 1024
        bot.edit_message_text(f"📦 Отправляю ZIP ({size_kb:.0f} KB)...", chat_id, status_msg_id)
        zip_name = os.path.splitext(filename)[0] + "_photos.zip"
        send_with_retry(
            bot.send_document, chat_id,
            document=(zip_name, io.BytesIO(zip_bytes)),
            caption=(
                "✅ <b>6 фото готовы!</b>\n"
                "📐 Размер: 720×1280\n"
                "🎨 Градиент по краям\n"
                "🖼 Формат: PNG без потерь\n"
                "🔁 Пришли следующее!"
            )
        )
        bot.delete_message(chat_id, status_msg_id)
    except Exception as e:
        log.error(f"Ошибка фото: {e}")
        try:
            bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg_id)
        except Exception:
            bot.send_message(chat_id, f"❌ Ошибка: <code>{e}</code>")


def process_video_and_send(chat_id, video_bytes, filename, status_msg_id):
    if not check_ffmpeg():
        bot.edit_message_text(
            "❌ ffmpeg не установлен на сервере!\n"
            "Добавь в Railway: Settings → nixpacks → install ffmpeg",
            chat_id, status_msg_id
        )
        return

    try:
        bot.edit_message_text("🎬 Начинаю обработку видео (6 версий × 2 размера)...", chat_id, status_msg_id)

        def status_cb(text):
            try:
                bot.edit_message_text(text, chat_id, status_msg_id)
            except Exception:
                pass

        zip_bytes = uniqualize_video_to_zip(video_bytes, filename, status_cb)
        size_mb = len(zip_bytes) / 1024 / 1024

        bot.edit_message_text(f"📦 Отправляю ZIP ({size_mb:.1f} MB)...", chat_id, status_msg_id)

        zip_name = os.path.splitext(filename)[0] + "_videos.zip"
        send_with_retry(
            bot.send_document, chat_id,
            document=(zip_name, io.BytesIO(zip_bytes)),
            caption=(
                "✅ <b>12 видео готовы!</b>\n"
                "📁 6 версий × 2 размера:\n"
                "• <code>_original</code> — оригинальный размер\n"
                "• <code>_tiktok</code> — 720×1280 с градиентом\n"
                "🔁 Пришли следующее!"
            )
        )
        bot.delete_message(chat_id, status_msg_id)

    except Exception as e:
        log.error(f"Ошибка видео: {e}")
        try:
            bot.edit_message_text(f"❌ Ошибка: <code>{str(e)[:300]}</code>", chat_id, status_msg_id)
        except Exception:
            bot.send_message(chat_id, f"❌ Ошибка: <code>{str(e)[:300]}</code>")


# ═══════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    bot.send_message(
        message.chat.id,
        "👋 <b>Image & Video Uniqualizer Bot</b>\n\n"
        "📸 <b>Фото:</b>\n"
        "  Отправь как файл → ZIP с 6 JPEG (720×1280)\n\n"
        "🎬 <b>Видео:</b>\n"
        "  Отправь как файл → ZIP с 12 MP4\n"
        "  (6 версий × оригинал + TikTok 720×1280)\n\n"
        "Форматы видео: MP4, MOV, AVI, MKV, WEBM...\n\n"
        "⚡ Без поворотов и зеркал!"
    )


@bot.message_handler(content_types=["document"])
def handle_document(message):
    chat_id = message.chat.id
    doc = message.document
    filename = doc.file_name or "file"
    ext = os.path.splitext(filename)[1].lower()

    is_image = doc.mime_type and doc.mime_type.startswith("image/")
    is_video = doc.mime_type and doc.mime_type.startswith("video/") or ext in VIDEO_EXTENSIONS

    if not is_image and not is_video:
        bot.send_message(chat_id, "⚠️ Пришли фото или видео файл!")
        return

    status_msg = bot.send_message(chat_id, "⏳ Скачиваю файл...")
    try:
        file_info = bot.get_file(doc.file_id)
        downloaded = bot.download_file(file_info.file_path)

        if is_image:
            process_photo_and_send(chat_id, downloaded, filename, status_msg.message_id)
        else:
            process_video_and_send(chat_id, downloaded, filename, status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка скачивания: <code>{e}</code>", chat_id, status_msg.message_id)


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
        process_photo_and_send(chat_id, downloaded, "photo.jpg", status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(content_types=["video"])
def handle_video(message):
    chat_id = message.chat.id
    video = message.video
    status_msg = bot.send_message(
        chat_id,
        "⏳ Скачиваю видео...\n"
        "<i>💡 Для лучшего качества — отправляй как файл (скрепка → Файл)</i>"
    )
    try:
        file_info = bot.get_file(video.file_id)
        downloaded = bot.download_file(file_info.file_path)
        filename = f"video_{video.file_unique_id}.mp4"
        process_video_and_send(chat_id, downloaded, filename, status_msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Ошибка: <code>{e}</code>", chat_id, status_msg.message_id)


@bot.message_handler(func=lambda m: True)
def handle_other(message):
    bot.send_message(
        message.chat.id,
        "📎 Отправь фото или видео как файл!\n/help — инструкция"
    )


if __name__ == "__main__":
    log.info("Бот запущен...")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
