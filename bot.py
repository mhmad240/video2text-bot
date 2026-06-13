# D:\bot_telegram\bot.py

# ==================== المكتبات ====================
import sys
import os
import asyncio
import tempfile
import logging
from pathlib import Path

# إضافة مسار المشروع الأصلي
PROJECT_PATH = r"D:\video-2-text-master"
sys.path.insert(0, PROJECT_PATH)

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

# دوال المعالجة من المشروع الأصلي
from businessLogic import (
    transcribe_audio_optimized,
    get_last_segments,
    format_text_with_sentences,
    format_with_timestamps,
    export_as_srt
)
from modules.model_loader import load_whisper_model
from modules.device_manager import get_device_info

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
device_info = None

def init_model():
    """تحميل النموذج عند بدء البوت"""
    global model, device_info
    
    logger.info("🔄 جاري تحميل النموذج...")
    device_info = get_device_info()
    logger.info(f"🖥️ الجهاز: {device_info['device']} | compute_type: {device_info['compute_type']}")
    model = load_whisper_model("base", device_info)
    logger.info("✅ تم تحميل النموذج بنجاح وجاهز للعمل")

# ==================== تخزين مؤقت للنتائج ====================
user_results = {}

def save_user_result(user_id, text, segments):
    """حفظ نتيجة التحويل للمستخدم"""
    user_results[user_id] = {
        'text': text,
        'segments': segments
    }
    logger.info(f"💾 تم حفظ النتيجة للمستخدم {user_id}: text={len(text)} حرف, segments={len(segments)}")

def get_user_result(user_id):
    """استرجاع نتيجة التحويل للمستخدم"""
    return user_results.get(user_id, None)

def clear_user_result(user_id):
    """مسح نتيجة المستخدم"""
    if user_id in user_results:
        del user_results[user_id]

# ==================== أوامر البوت ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start - ترحيب وشرح"""
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
    """أمر /help"""
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
    """أمر /models - عرض النماذج"""
    models_text = """
🧠 **النماذج المتاحة:**

• **tiny** - 39M - سريع جداً، دقة منخفضة
• **base** - 74M - متوازن ✅ (المستخدم حالياً)
• **small** - 244M - دقة جيدة
• **medium** - 769M - دقة عالية
• **large-v3** - 1.5B - الأفضل (للموقع فقط)

📌 البوت يستخدم نموذج **base** للتوازن بين السرعة والدقة
"""
    await update.message.reply_text(models_text)

# ==================== أزرار خيارات التنسيق ====================

def get_format_keyboard():
    """إنشاء أزرار خيارات التنسيق"""
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
    """معالجة اختيار التنسيق"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    choice = query.data
    
    # زر الخروج
    if choice == "exit":
        clear_user_result(user_id)
        await query.edit_message_text("👋 تم إنهاء الجلسة. أرسل فيديو جديد للبدء من جديد.")
        return
    
    # زر مشروع جديد
    if choice == "new_project":
        clear_user_result(user_id)
        await query.edit_message_text("🔄 تم مسح المشروع السابق. أرسل فيديو أو ملف صوتي جديد.")
        return
    
    # استرجاع النتيجة
    result = get_user_result(user_id)
    
    if not result:
        await query.edit_message_text("❌ انتهت الجلسة. أرسل فيديو جديد للمعالجة.")
        return
    
    text = result['text']
    segments = result['segments']
    
    logger.info(f"🔘 اختار المستخدم {user_id}: {choice}, segments={len(segments)}")
    
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
                        translated_seg = seg.copy()
                        translated_seg['text'] = translator.translate(seg['text'])
                        translated_segments.append(translated_seg)
                    except Exception as te:
                        logger.error(f"خطأ ترجمة segment: {te}")
                        translated_segments.append(seg)
                srt_content = export_as_srt(translated_segments)
                await send_srt_file(query, srt_content, "transcript_translated.srt", "🌐 ملف الترجمة المترجم (SRT)")
            except Exception as e:
                logger.error(f"فشلت الترجمة: {e}")
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
                        translated_seg = seg.copy()
                        translated_seg['text'] = translator.translate(seg['text'])
                        translated_segments.append(translated_seg)
                    except Exception as te:
                        logger.error(f"خطأ ترجمة segment: {te}")
                        translated_segments.append(seg)
                srt_content = export_as_srt(translated_segments)
                await send_srt_file(query, srt_content, "transcript_arabic.srt", "🇸🇦 ملف الترجمة العربية (SRT)")
            except Exception as e:
                logger.error(f"فشلت الترجمة للعربية: {e}")
                await query.edit_message_text(f"❌ فشلت الترجمة للعربية: {str(e)}")
                return
        else:
            await query.answer("⚠️ لا تتوفر بيانات الترجمة", show_alert=True)
            return
            
    elif choice == "format_text_only":
        await query.edit_message_text("✅ **النص المستخرج:**")
        await send_long_message(query.message, text)
    
    # العودة لقائمة الأزرار بعد التنفيذ
    await query.message.reply_text(
        "🎨 **اختر تنسيقاً آخر أو أنهِ الجلسة:**",
        reply_markup=get_format_keyboard()
    )

async def send_long_message(message, text):
    """إرسال نص طويل مقسم لعدة رسائل"""
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.reply_text(part)
    else:
        await message.reply_text(text)

async def send_srt_file(query, srt_content, filename, caption):
    """حفظ وإرسال ملف SRT"""
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

# ==================== معالجة الفيديو ====================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الفيديو وتحويله إلى نص"""
    user = update.effective_user
    message = update.message
    
    video = message.video
    file_size = video.file_size
    
    if file_size > MAX_VIDEO_SIZE:
        await message.reply_text(
            f"⚠️ حجم الفيديو كبير جداً ({file_size / 1024 / 1024:.1f} ميجا)\n"
            f"الحد الأقصى: 50 ميجا\n\n"
            f"🔗 استخدم موقعنا للملفات الكبيرة:\n{WEBSITE_URL}"
        )
        return
    
    status_msg = await message.reply_text("⏳ جاري تحميل الفيديو...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الفيديو...")
        video_file = await context.bot.get_file(video.file_id)
        
        temp_video_path = os.path.join(tempfile.gettempdir(), f"{video.file_unique_id}.mp4")
        await video_file.download_to_drive(temp_video_path)
        
        await status_msg.edit_text("🎵 جاري استخراج الصوت وتحويله إلى نص...")
        
        def progress_callback(progress):
            pass
        
        result = transcribe_audio_optimized(
            source=temp_video_path,
            model=model,
            device_info=device_info,
            progress_callback=progress_callback
        )
        
        try:
            os.remove(temp_video_path)
        except:
            pass
        
        await process_result(result, user.id, status_msg, message)
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"خطأ في معالجة الفيديو: {error_msg}")
        
        if "too big" in error_msg.lower():
            await status_msg.edit_text(
                f"⚠️ تعذر تحميل الفيديو - ربما حجمه كبير جداً\n"
                f"🔗 جرب موقعنا للملفات الكبيرة:\n{WEBSITE_URL}"
            )
        else:
            await status_msg.edit_text(f"❌ حدث خطأ: {error_msg}")

# ==================== معالجة الصوت ====================

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال ملف صوتي وتحويله إلى نص"""
    user = update.effective_user
    message = update.message
    
    audio = message.audio or message.voice
    file_size = audio.file_size
    
    if file_size > MAX_VIDEO_SIZE:
        await message.reply_text(
            f"⚠️ حجم الملف كبير جداً ({file_size / 1024 / 1024:.1f} ميجا)\n"
            f"الحد الأقصى: 50 ميجا\n\n"
            f"🔗 استخدم موقعنا للملفات الكبيرة:\n{WEBSITE_URL}"
        )
        return
    
    status_msg = await message.reply_text("⏳ جاري تحميل الملف الصوتي...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الملف الصوتي...")
        audio_file = await context.bot.get_file(audio.file_id)
        
        ext = ".ogg" if message.voice else ".mp3"
        temp_audio_path = os.path.join(tempfile.gettempdir(), f"{audio.file_unique_id}{ext}")
        await audio_file.download_to_drive(temp_audio_path)
        
        await status_msg.edit_text("🎵 جاري تحويل الصوت إلى نص...")
        
        def progress_callback(progress):
            pass
        
        result = transcribe_audio_optimized(
            source=temp_audio_path,
            model=model,
            device_info=device_info,
            progress_callback=progress_callback
        )
        
        try:
            os.remove(temp_audio_path)
        except:
            pass
        
        await process_result(result, user.id, status_msg, message)
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"خطأ في معالجة الملف الصوتي: {error_msg}")
        await status_msg.edit_text(f"❌ حدث خطأ: {error_msg}")

# ==================== معالجة روابط يوتيوب ====================

async def handle_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال رابط يوتيوب ومعالجته"""
    user = update.effective_user
    message = update.message
    url = message.text.strip()
    
    status_msg = await message.reply_text("⏳ جاري معالجة رابط اليوتيوب...")
    
    try:
        await status_msg.edit_text("📥 جاري تحميل الفيديو من يوتيوب...")
        
        def progress_callback(progress):
            pass
        
        result = transcribe_audio_optimized(
            source=url,
            model=model,
            device_info=device_info,
            progress_callback=progress_callback
        )
        
        await process_result(result, user.id, status_msg, message)
            
    except Exception as e:
        logger.error(f"خطأ في معالجة رابط اليوتيوب: {e}")
        await status_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

# ==================== دالة معالجة النتيجة المشتركة ====================

async def process_result(result, user_id, status_msg, message):
    """معالجة نتيجة التحويل وإظهار خيارات التنسيق"""
    
    # استخراج النص والـ segments
    if isinstance(result, dict):
        result_text = result.get('text', '')
        segments_data = result.get('segments', [])
    else:
        # إذا كانت النتيجة نص فقط، نبحث عن segments في المتغير العام
        result_text = result
        segments_data = get_last_segments()
        if not segments_data:
            segments_data = []
    
    logger.info(f"📊 نتيجة المعالجة: text={len(result_text)} حرف, segments={len(segments_data)}")
    
    if result_text and not result_text.startswith("❌"):
        save_user_result(user_id, result_text, segments_data)
        
        await status_msg.delete()
        
        preview = result_text[:500] + "..." if len(result_text) > 500 else result_text
        await message.reply_text(f"✅ **تم التحويل بنجاح!**\n\n{preview}")
        
        await message.reply_text(
            "🎨 **اختر تنسيق الإخراج:**",
            reply_markup=get_format_keyboard()
        )
    else:
        await status_msg.edit_text(f"❌ فشل التحويل: {result_text}")

# ==================== معالجة النصوص الأخرى ====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة النصوص الأخرى"""
    message = update.message
    text = message.text.strip()
    
    if "youtube.com" in text or "youtu.be" in text:
        await handle_youtube_link(update, context)
    else:
        await message.reply_text(
            "🎬 أرسل فيديو، ملف صوتي، أو رابط يوتيوب للتحويل إلى نص\n"
            "استخدم /help للمساعدة"
        )

# ==================== معالج الأخطاء ====================

async def error_handler(update, context):
    """معالجة الأخطاء"""
    error = str(context.error)
    if "not modified" in error.lower():
        return
    logger.error(f"Update {update} caused error {context.error}")

# ==================== التشغيل ====================

def main():
    """تشغيل البوت"""
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