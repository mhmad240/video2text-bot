# 🎬 Video2Text Bot

بوت تلجرام لتحويل الفيديو والصوت إلى نص مكتوب باستخدام الذكاء الاصطناعي (OpenAI Whisper).

## 🔗 الروابط

| الوصف | الرابط |
|-------|--------|
| 🤖 البوت على تلجرام | [@VideoToText01Bot](https://t.me/VideoToText01Bot) |
| 🌐 تطبيق الويب | [video-2-text-s01.streamlit.app](https://video-2-text-s01.streamlit.app/) |
| 📂 المستودع | [GitHub](https://github.com/mhmad240/video2text-bot) |
| 📁 المشروع الأصلي | [video-2-text](https://github.com/mhmad240/video-2-text) |
| 🌐 تطبيق الويب | [Railway](https://railway.com/dashboard) |
| 🌐 تطبيق الويب | [المطور](https://github.com/mhmad240) |

## ✨ الميزات

- 🎥 تحويل الفيديو إلى نص (حتى 50 ميجا)
- 🎵 دعم الملفات الصوتية (MP3, WAV, Voice)
- 🔗 دعم روابط يوتيوب
- 📝 خيارات تنسيق متعددة:
  - تنسيق الجمل
  - عرض Timestamps
  - ملف SRT أصلي
  - ملف SRT مترجم للإنجليزية
  - ملف SRT مترجم للعربية
  - نص فقط

## 🚀 التشغيل المحلي

```bash
git clone https://github.com/mhmad240/video2text-bot.git
cd video2text-bot
pip install -r requirements.txt
أنشئ ملف config.py:

python
TOKEN = "توكن_البوت_هنا"
شغّل:

bash
python bot.py
🖥️ النشر على السيرفر
المشروع جاهز للنشر على **Railway** باستخدام Dockerfile المرفق.

🧠 النموذج
يستخدم openai-whisper بنموذج tiny (39M) للذاكرة المحدودة. يمكن تغييره إلى base أو small محلياً.

👤 المطور
Mhmad240

اضغط **Commit new file**.
