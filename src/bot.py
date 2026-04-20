import os
import asyncio
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from google import genai

from downloader import VideoDownloader
from database import Database

load_dotenv()

# Инициализация клиентов
client = genai.Client(api_key=os.getenv("GEMINI_KEY"))
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
dl = VideoDownloader()
db = Database()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await db.log_request(message.from_user.id, message.from_user.username)
    await message.answer(f"Привет, {message.from_user.full_name}! Отправь мне ссылку на YouTube, и я помогу скачать или пересказать видео.")

@dp.message(F.text.contains("youtube.com") | F.text.contains("youtu.be"))
async def handle_link(message: types.Message):
    url = message.text
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🎬 Видео (MP4)", callback_data=f"dl_video|{url}"))
    builder.row(types.InlineKeyboardButton(text="🎵 Аудио (MP3)", callback_data=f"dl_audio|{url}"))
    builder.row(types.InlineKeyboardButton(text="📝 AI Пересказ", callback_data=f"ai_sum|{url}"))
    await message.answer("Что нужно сделать?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def process_download(callback: types.CallbackQuery):
    action, url = callback.data.split("|", 1)
    mode = "video" if action == "dl_video" else "audio"
    
    status_msg = await callback.message.answer("🚀 Загружаю файл, подождите...")
    file_path = await dl.download_video(url, mode=mode)
    
    if not file_path:
        await status_msg.edit_text("❌ Ошибка при скачивании.")
        return

    try:
        input_file = types.FSInputFile(file_path)
        if mode == "video":
            await callback.message.answer_video(input_file)
        else:
            await callback.message.answer_audio(input_file)
    finally:
        # Stateless: удаляем файл с диска VPS
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

@dp.callback_query(F.data.startswith("ai_sum"))
async def process_ai(callback: types.CallbackQuery):
    url = callback.data.split("|", 1)[1]
    status_msg = await callback.message.answer("📥 Скачиваю видео для нейронки...")
    
    # 1. Сначала качаем видео (в низком качестве, чтобы быстрее)
    file_path = await dl.download_video(url, mode="video")
    
    if not file_path:
        await status_msg.edit_text("❌ Не удалось скачать видео для анализа.")
        return

    try:
        await status_msg.edit_text("🚀 Загружаю видео в Gemini API...")
        
        # 2. Загружаем файл в Google File API
        video_file = client.files.upload(file=file_path)
        
        # 3. Ждем, пока Google его "переварит"
        await status_msg.edit_text("🧠 ИИ смотрит видео... подожди немного.")
        
        # Простая проверка статуса
        import time
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = client.files.get(name=video_file.name)

        # 4. Просим проанализировать именно ФАЙЛ
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                video_file,
                "Сделай подробный разбор этого видео. О чем в нем говорят? Какие ключевые моменты ты видишь?"
            ]
        )
        
        summary_text = response.text
        if len(summary_text) > 4000:
            summary_text = summary_text[:4000] + "...\n\n(Текст обрезан из-за лимитов Telegram)"

        await callback.message.answer(f"🤖 **Разбор видео:**\n\n{summary_text}")
        
        # 5. Удаляем файл из Google Cloud (чтобы не копился мусор)
        client.files.delete(name=video_file.name)

    except Exception as e:
        print(f"Ошибка мультимодальности: {e}")
        await callback.message.answer("❌ ИИ не смог посмотреть видео. Возможно, файл слишком большой.")
    finally:
        # Чистим локальный файл на VPS
        if os.path.exists(file_path):
            os.remove(file_path)
        await status_msg.delete()

async def main():
    print("Подключение к базе данных...")
    await db.connect()
    print("Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
