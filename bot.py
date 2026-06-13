# D:\bot_telegram\bot.py

# ==================== المكتبات ====================
import sys
import os
import asyncio
import tempfile
import logging
from pathlib import Path

# مكتبات تلجرام
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# Whisper
import whisper

# دوال التنسيق
# دوال التنسيق - مضمنة في الكود
# ==================== الإعدادات ====================
import config

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50 ميجا
WEBSITE_URL = "https://video-2-text-s01.streamlit.app/"

# ==================== تحميل النموذج مسبقاً ====================
model = None

def init_model():
    """تحميل النموذج عند بدء البوت"""
    global model
    
    logger.info("🔄 جاري تحميل النموذج...")
    model = whisper.load_model("base")
    logger.info("✅ تم تحميل النموذج بنجاح وجاهز للعمل")

# ==================== تخزين مؤقت للنتائج ====================
user_results = {}

def save_user_result(user_id, text, segments):
    user_results[user_id] = {
        'text': text,
        'segments': segments
    }

def get_user_result(user_id):
    return user_results.get(user_id, None)

def clear_user_result(user_id):
    if user_id in user_results:
        del user_results[user_id]

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome_text = f"""
👋 مرحباً {user.first_name}!

🎬 **بوت تحويل الفيديو إلى نص**

📹 أرسل فيديو (حتى 50 ميجا) أو رابط يوتيوب
🎵 أو أرسل ملف صوتي (MP3, WAV, Voice)
📝 سأقوم باستخراج الصوت وتحويله إلى نص مكتوب

⚠️ للملفات الأكبر من 50 ميجا:
استخدم موقعنا: {WEBSITE_URL}

الأوامر المتاحة:
/start - البدء
/help - المساعدة
/models - النماذج المتاحة
"""
    await update.message.reply_text(welcome_text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = f"""
📚 **المساعدة**

1️⃣ أرسل فيديو مباشرة (MP4, AVI, MOV...)
2️⃣ أرسل ملف صوتي (MP3, WAV, Voice)
3️⃣ أو أرسل رابط فيديو يوتيوب
4️⃣ انتظر حتى اكتمال المعالجة
5️⃣ اختر تنسيق النص المطلوب
6️⃣ استلم النص أو ملف الترجمة

⚠️ الحد الأقصى: 50 ميجا
🔗 للملفات الأكبر: {WEBSITE_URL}

للاستفسار: @mhmad240
"""
    await update.message.reply_text(help_text)

async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    models_text = """
🧠 **النماذج المتاحة:**

• **tiny** - 39M - سريع جداً
• **base** - 74M - متوازن ✅ (المستخدم حالياً)
• **small** - 244M - دقة جيدة
• **medium** - 769M - دقة عالية
• **large** - 1.5B - الأفضل

📌 البوت يستخدم نموذج **base** للتوازن بين السرعة والدقة
"""
    await update.message.reply_text(models_text)

# ==================== أزرار خيارات التنسيق ====================

def get_format_keyboard():
    keyboard = [
        [InlineKeyboardButton("📝 تنسيق الجمل", callback_data="format_sentences")],
        [InlineKeyboardButton("⏱️ عرض Timestamps", callback_data="format_timestamps")],
        [InlineKeyboardButton("📄 أصلي SRT", callback_data="format_srt_original")],
        [InlineKeyboardButton("🌐 مترجم SRT", callback_data="format_srt_translated")],
        [InlineKeyboardButton("🇸🇦 عربي SRT تحميل", callback_data="format_srt_arabic")],
        [InlineKeyboardButton("📋 نص فقط", callback_data="format_text_only")],
        [
            InlineKeyboardButton("🔄 مشروع جديد", callback_data="new_project"),
            InlineKeyboardButton("🚪 خروج", callback_data="exit")
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    if choice == "exit":
        clear_user_result(user_id)
        await query.edit_message_text("👋 تم إنهاء الجلسة. أرسل فيديو جديد للبدء من جديد.")
        return
    
    if choice == "new_project":
        clear_user_result(user_id)
        await query.edit_message_text("🔄 تم مسح المشروع السابق. أرسل فيديو أو ملف صوتي جديد.")
        return
    
    result = get_user_result(user_id)
    
    if not result:
        await query.edit_message_text("❌ انتهت الجلسة. أرسل فيديو جديد للمعالجة.")
        return
    
    text = result['text']
    segments = result['segments']
    
    if choice == "format_sentences":
        formatted = format_text_with_sentences(text)
        await query.edit_message_text("✅ **تنسيق الجمل:**")
        await send_long_message(query.message, formatted)
        
    elif choice == "format_timestamps":
        if segments and len(segments) > 0:
            formatted = format_with_timestamps(segments)
            await query.edit_message_text("✅ **عرض Timestamps:**")
            await send_long_message(query.message, formatted)
        else:
            await query.answer("⚠️ لا تتوفر بيانات التوقيت", show_alert=True)
            return
            
    elif choice == "format_srt_original":
        if segments and len(segments) > 0:
            srt_content = export_as_srt(segments)
            await send_srt_file(query, srt_content, "transcript_original.srt", "📄 ملف الترجمة الأصلي (SRT)")
        else:
            await query.answer("⚠️ لا تتوفر بيانات الترجمة", show_alert=True)
            return
            
    elif choice == "format_srt_translated":
        if segments and len(segments) > 0:
            try:
                await query.edit_message_text("🌐 جاري الترجمة...")
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='auto', target='en')
                translated_segments = []
                for seg in segments:
                    try:
                        ts = seg.copy()
                        ts['text'] = translator.translate(seg['text'])
                        translated_segments.append(ts)
                    except:
                        translated_segments.append(seg)
                srt_content = export_as_srt(translated_segments)
                await send_srt_file(query, srt_content, "transcript_translated.srt", "🌐 ملف الترجمة المترجم (SRT)")
            except Exception as e:
                await query.edit_message_text(f"❌ فشلت الترجمة: {str(e)}")
                return
        else:
            await query.answer("⚠️ لا تتوفر بيانات الترجمة", show_alert=True)
            return
            
    elif choice == "format_srt_arabic":
        if segments and len(segments) > 0:
            try:
                await query.edit_message_text("🇸🇦 جاري الترجمة للعربية...")
                from deep_translator import GoogleTranslator
                translator = GoogleTranslator(source='auto', target='ar')
                translated_segments = []
                for seg in segments:
                    try:
                        ts = seg.copy()
                        ts['text'] = translator.translate(seg['text'])
                        translated_segments.append(ts)
                    except:
                        translated_segments.append(seg)
                srt_content = export_as_srt(translated_segments)
                await send_srt_file(query, srt_content, "transcript_arabic.srt", "🇸🇦 ملف الترجمة العربية (SRT)")
            except Exception as e:
                await query.edit_message_text(f"❌ فشلت الترجمة للعربية: {str(e)}")
                return
        else:
            await query.answer("⚠️ لا تتوفر بيانات الترجمة", show_alert=True)
            return
            
    elif choice == "format_text_only":
        await query.edit_message_text("✅ **النص المستخرج:**")
        await send_long_message(query.message, text)
    
    await query.message.reply_text(
        "🎨 **اختر تنسيقاً آخر أو أنهِ الجلسة:**",
        reply_markup=get_format_keyboard()
    )

async def send_long_message(message, text):
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part)
    else:
        await message.reply_text(text)

async def send_srt_file(query, srt_content, filename, caption):
    srt_path = os.path.join(tempfile.gettempdir(), f"srt_{query.from_user.id}.srt")
    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_content)
    
    await query.message.reply_document(
        document=open(srt_path, "rb"),
        filename=filename,
        caption=caption
    )
    
    await query.edit_message_text(f"✅ {caption}")
    
    try:
        os.remove(srt_path)
    except:
        pass

# ==================== معالجة الملفات ====================

def extract_audio(video_path):
    """استخراج الصوت من الفيديو"""
    from moviepy.editor import VideoFileClip
    
    temp_dir = tempfile.gettempdir()
    audio_path = os.path.join(temp_dir, f"{os.path.basename(video_path)}_audio.wav")
    
    video_clip = VideoFileClip(video_path)
    audio_clip = video_clip.audio
    audio_clip.write_audiofile(audio_path, verbose=False, logger=None)
    audio_clip.close()
    video_clip.close()
    
    return audio_path

def download_youtube_audio(url):
    """تحميل الصوت من يوتيوب"""
    import yt_dlp
    
    temp_dir = tempfile.gettempdir()
    output_path = os.path.join(temp_dir, "youtube_audio_%(id)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_path,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info['id']
    
    audio_path = os.path.join(temp_dir, f"youtube_audio_{video_id}.wav")
    return audio_path

def transcribe_audio(audio_path):
    """تحويل الصوت إلى نص باستخدام whisper"""
    result = model.transcribe(audio_path)
    
    text = result['text']
    segments = []
    for seg in result['segments']:
        segments.append({
            'start': seg['start'],
            'end': seg['end'],
            'text': seg['text'].strip()
        })
    
    return {
        'text': text,
        'segments': segments
    }

async def process_result(result, user_id, status_msg, message):
    """معالجة نتيجة التحويل"""
    text = result['text']
    segments = result['segments']
    
    if text:
        save_user_result(user_id, text, segments)
        await status_msg.delete()
        
        preview = text[:500] + "..." if len(text) > 500 else text
        await message.reply_text(f"✅ **تم التحويل بنجاح!**\n\n{preview}")
        
        await message.reply_text(
            "🎨 **اختر تنسيق الإخراج:**",
            reply_markup=get_format_keyboard()
        )
    else:
        await status_msg.edit_text("❌ لم يتم استخراج أي نص")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    video = message.video
    
    if video.file_size > MAX_VIDEO_SIZE:
        await message.reply_text(
            f"⚠️ حجم الفيديو كبير جداً\n🔗 استخدم موقعنا: {WEBSITE_URL}"
        )
        return
    
    status_msg = await message.reply_text("⏳ جاري التحميل...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الفيديو...")
        video_file = await context.bot.get_file(video.file_id)
        
        temp_video = os.path.join(tempfile.gettempdir(), f"{video.file_unique_id}.mp4")
        await video_file.download_to_drive(temp_video)
        
        await status_msg.edit_text("🎵 جاري استخراج الصوت...")
        audio_path = extract_audio(temp_video)
        
        await status_msg.edit_text("🧠 جاري التحويل إلى نص...")
        result = transcribe_audio(audio_path)
        
        try:
            os.remove(temp_video)
            os.remove(audio_path)
        except:
            pass
        
        await process_result(result, user.id, status_msg, message)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    audio = message.audio or message.voice
    
    if audio.file_size > MAX_VIDEO_SIZE:
        await message.reply_text(f"⚠️ حجم الملف كبير جداً\n🔗 استخدم موقعنا: {WEBSITE_URL}")
        return
    
    status_msg = await message.reply_text("⏳ جاري التحميل...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الصوت...")
        audio_file = await context.bot.get_file(audio.file_id)
        
        ext = ".ogg" if message.voice else ".mp3"
        temp_audio = os.path.join(tempfile.gettempdir(), f"{audio.file_unique_id}{ext}")
        await audio_file.download_to_drive(temp_audio)
        
        await status_msg.edit_text("🧠 جاري التحويل إلى نص...")
        result = transcribe_audio(temp_audio)
        
        try:
            os.remove(temp_audio)
        except:
            pass
        
        await process_result(result, user.id, status_msg, message)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    url = message.text.strip()
    
    status_msg = await message.reply_text("⏳ جاري معالجة الرابط...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الفيديو من يوتيوب...")
        audio_path = download_youtube_audio(url)
        
        await status_msg.edit_text("🧠 جاري التحويل إلى نص...")
        result = transcribe_audio(audio_path)
        
        try:
            os.remove(audio_path)
        except:
            pass
        
        await process_result(result, user.id, status_msg, message)
        
    except Exception as e:
        logger.error(f"خطأ: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "youtube.com" in text or "youtu.be" in text:
        await handle_youtube_link(update, context)
    else:
        await update.message.reply_text("🎬 أرسل فيديو، ملف صوتي، أو رابط يوتيوب للتحويل إلى نص\nاستخدم /help للمساعدة")

async def error_handler(update, context):
    error = str(context.error)
    if "not modified" in error.lower():
        return
    logger.error(f"Error: {context.error}")

# ==================== التشغيل ====================

def main():
    init_model()
    
    app = Application.builder().token(config.TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("models", models_command))
    app.add_handler(CallbackQueryHandler(format_callback))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    
    logger.info("🤖 البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
