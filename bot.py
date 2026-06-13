# bot.py - Video2Text Telegram Bot
import os
import tempfile
import logging
import whisper
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ==================== دوال التنسيق ====================
import re

def format_text_with_sentences(text):
    sentences = re.split(r'([.!?]+\s+)', text)
    formatted = []
    current = ""
    for part in sentences:
        current += part
        if re.match(r'[.!?]+\s+', part) or part == sentences[-1]:
            if current.strip():
                formatted.append(current.strip())
            current = ""
    return "\n".join(formatted)

def format_with_timestamps(segments):
    lines = []
    for seg in segments:
        s = seg['start']
        h, m = int(s//3600), int((s%3600)//60)
        sec = int(s%60)
        lines.append(f"[{h:02d}:{m:02d}:{sec:02d}] {seg['text']}")
    return "\n".join(lines)

def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def export_as_srt(segments):
    lines = []
    for i, seg in enumerate(segments, 1):
        start = format_srt_timestamp(seg['start'])
        end = format_srt_timestamp(seg['end'])
        lines.append(str(i))
        lines.append(f"{start} --> {end}")
        lines.append(seg['text'])
        lines.append("")
    return "\n".join(lines)

# ==================== الإعدادات ====================
import config

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_VIDEO_SIZE = 50 * 1024 * 1024
WEBSITE_URL = "https://video-2-text-s01.streamlit.app/"

# ==================== النموذج ====================
model = None

def init_model():
    global model
    logger.info("🔄 جاري تحميل النموذج...")
    model = whisper.load_model("base")
    logger.info("✅ النموذج جاهز")

# ==================== تخزين النتائج ====================
user_results = {}

def save_result(uid, text, segments):
    user_results[uid] = {'text': text, 'segments': segments}

def get_result(uid):
    return user_results.get(uid)

def clear_result(uid):
    if uid in user_results:
        del user_results[uid]

# ==================== أزرار التنسيق ====================
def get_keyboard():
    kb = [
        [InlineKeyboardButton("📝 تنسيق الجمل", callback_data="fmt_sent")],
        [InlineKeyboardButton("⏱️ عرض Timestamps", callback_data="fmt_time")],
        [InlineKeyboardButton("📄 أصلي SRT", callback_data="fmt_srt")],
        [InlineKeyboardButton("🌐 مترجم SRT", callback_data="fmt_srt_en")],
        [InlineKeyboardButton("🇸🇦 عربي SRT", callback_data="fmt_srt_ar")],
        [InlineKeyboardButton("📋 نص فقط", callback_data="fmt_text")],
        [InlineKeyboardButton("🔄 مشروع جديد", callback_data="new"),
         InlineKeyboardButton("🚪 خروج", callback_data="exit")],
    ]
    return InlineKeyboardMarkup(kb)

# ==================== أوامر البوت ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""
👋 مرحباً {update.effective_user.first_name}!

🎬 بوت تحويل الفيديو إلى نص
📹 أرسل فيديو (حتى 50 ميجا)، ملف صوتي، أو رابط يوتيوب

⚠️ للملفات الأكبر: {WEBSITE_URL}
""")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""
📚 أرسل فيديو/صوت/رابط يوتيوب ثم اختر التنسيق
⚠️ الحد: 50 ميجا | 🔗 {WEBSITE_URL}
""")

async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 النموذج المستخدم: base (74M)")

# ==================== معالج الأزرار ====================
async def btn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    c = q.data

    if c == "exit":
        clear_result(uid)
        await q.edit_message_text("👋 تم إنهاء الجلسة")
        return
    if c == "new":
        clear_result(uid)
        await q.edit_message_text("🔄 أرسل ملفاً جديداً")
        return

    r = get_result(uid)
    if not r:
        await q.edit_message_text("❌ انتهت الجلسة")
        return

    t, seg = r['text'], r['segments']

    if c == "fmt_sent":
        await q.edit_message_text("✅ تنسيق الجمل:")
        await send_long(q.message, format_text_with_sentences(t))
    elif c == "fmt_time":
        if seg:
            await q.edit_message_text("✅ Timestamps:")
            await send_long(q.message, format_with_timestamps(seg))
        else:
            await q.answer("⚠️ لا تتوفر بيانات التوقيت", show_alert=True)
            return
    elif c == "fmt_srt":
        if seg:
            await send_srt(q, export_as_srt(seg), "original.srt", "📄 SRT أصلي")
        else:
            await q.answer("⚠️ لا تتوفر بيانات", show_alert=True)
            return
    elif c == "fmt_srt_en":
        if seg:
            await q.edit_message_text("🌐 جاري الترجمة...")
            try:
                from deep_translator import GoogleTranslator
                tr = GoogleTranslator(source='auto', target='en')
                ns = []
                for s in seg:
                    try:
                        x = s.copy()
                        x['text'] = tr.translate(s['text'])
                        ns.append(x)
                    except:
                        ns.append(s)
                await send_srt(q, export_as_srt(ns), "translated.srt", "🌐 SRT مترجم")
            except Exception as e:
                await q.edit_message_text(f"❌ فشلت الترجمة: {e}")
                return
        else:
            await q.answer("⚠️ لا تتوفر بيانات", show_alert=True)
            return
    elif c == "fmt_srt_ar":
        if seg:
            await q.edit_message_text("🇸🇦 جاري الترجمة للعربية...")
            try:
                from deep_translator import GoogleTranslator
                tr = GoogleTranslator(source='auto', target='ar')
                ns = []
                for s in seg:
                    try:
                        x = s.copy()
                        x['text'] = tr.translate(s['text'])
                        ns.append(x)
                    except:
                        ns.append(s)
                await send_srt(q, export_as_srt(ns), "arabic.srt", "🇸🇦 SRT عربي")
            except Exception as e:
                await q.edit_message_text(f"❌ فشلت الترجمة: {e}")
                return
        else:
            await q.answer("⚠️ لا تتوفر بيانات", show_alert=True)
            return
    elif c == "fmt_text":
        await q.edit_message_text("✅ النص:")
        await send_long(q.message, t)

    await q.message.reply_text("🎨 اختر تنسيقاً آخر:", reply_markup=get_keyboard())

async def send_long(msg, text):
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await msg.reply_text(text[i:i+4000])
    else:
        await msg.reply_text(text)

async def send_srt(q, content, fname, cap):
    p = os.path.join(tempfile.gettempdir(), f"srt_{q.from_user.id}.srt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    await q.message.reply_document(open(p, "rb"), filename=fname, caption=cap)
    await q.edit_message_text(f"✅ {cap}")
    try:
        os.remove(p)
    except:
        pass

# ==================== استخراج الصوت ====================
def extract_audio(video_path):
    from moviepy.editor import VideoFileClip
    out = os.path.join(tempfile.gettempdir(), f"{os.path.basename(video_path)}_audio.wav")
    clip = VideoFileClip(video_path)
    clip.audio.write_audiofile(out, verbose=False, logger=None)
    clip.close()
    return out

def download_yt(url):
    import yt_dlp
    d = tempfile.gettempdir()
    out = os.path.join(d, "yt_%(id)s.%(ext)s")
    opts = {'format': 'bestaudio/best', 'outtmpl': out, 'quiet': True,
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}]}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
    return os.path.join(d, f"yt_{info['id']}.wav")

def transcribe(path):
    res = model.transcribe(path)
    return {
        'text': res['text'],
        'segments': [{'start': s['start'], 'end': s['end'], 'text': s['text'].strip()} for s in res['segments']]
    }

async def proc_result(result, uid, sm, msg):
    if result['text']:
        save_result(uid, result['text'], result['segments'])
        await sm.delete()
        prev = result['text'][:500] + ("..." if len(result['text']) > 500 else "")
        await msg.reply_text(f"✅ تم التحويل!\n\n{prev}")
        await msg.reply_text("🎨 اختر التنسيق:", reply_markup=get_keyboard())
    else:
        await sm.edit_text("❌ لم يتم استخراج نص")

# ==================== معالجات الملفات ====================
async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    v = m.video
    if v.file_size > MAX_VIDEO_SIZE:
        await m.reply_text(f"⚠️ حجم كبير\n🔗 {WEBSITE_URL}")
        return
    sm = await m.reply_text("⏳ جاري التحميل...")
    try:
        await sm.edit_text("📥 تحميل...")
        f = await context.bot.get_file(v.file_id)
        tv = os.path.join(tempfile.gettempdir(), f"{v.file_unique_id}.mp4")
        await f.download_to_drive(tv)
        await sm.edit_text("🎵 استخراج الصوت...")
        ap = extract_audio(tv)
        await sm.edit_text("🧠 تحويل إلى نص...")
        res = transcribe(ap)
        try:
            os.remove(tv); os.remove(ap)
        except:
            pass
        await proc_result(res, update.effective_user.id, sm, m)
    except Exception as e:
        logger.error(str(e))
        await sm.edit_text(f"❌ خطأ: {e}")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    a = m.audio or m.voice
    if a.file_size > MAX_VIDEO_SIZE:
        await m.reply_text(f"⚠️ حجم كبير\n🔗 {WEBSITE_URL}")
        return
    sm = await m.reply_text("⏳ جاري التحميل...")
    try:
        await sm.edit_text("📥 تحميل...")
        f = await context.bot.get_file(a.file_id)
        ext = ".ogg" if m.voice else ".mp3"
        ta = os.path.join(tempfile.gettempdir(), f"{a.file_unique_id}{ext}")
        await f.download_to_drive(ta)
        await sm.edit_text("🧠 تحويل إلى نص...")
        res = transcribe(ta)
        try:
            os.remove(ta)
        except:
            pass
        await proc_result(res, update.effective_user.id, sm, m)
    except Exception as e:
        logger.error(str(e))
        await sm.edit_text(f"❌ خطأ: {e}")

async def handle_yt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    url = m.text.strip()
    sm = await m.reply_text("⏳ معالجة الرابط...")
    try:
        await sm.edit_text("📥 تحميل من يوتيوب...")
        ap = download_yt(url)
        await sm.edit_text("🧠 تحويل إلى نص...")
        res = transcribe(ap)
        try:
            os.remove(ap)
        except:
            pass
        await proc_result(res, update.effective_user.id, sm, m)
    except Exception as e:
        logger.error(str(e))
        await sm.edit_text(f"❌ خطأ: {e}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    if "youtube.com" in t or "youtu.be" in t:
        await handle_yt(update, context)
    else:
        await update.message.reply_text("🎬 أرسل فيديو، صوت، أو رابط يوتيوب")

async def err_handler(update, context):
    e = str(context.error)
    if "not modified" not in e.lower():
        logger.error(str(context.error))

# ==================== رئيسي ====================
def main():
    init_model()
    app = Application.builder().token(config.TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CallbackQueryHandler(btn_handler))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(err_handler)
    logger.info("🤖 البوت يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
