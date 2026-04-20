import yt_dlp
import os
import asyncio

class VideoDownloader:
    def __init__(self, download_folder="downloads"):
        self.download_folder = download_folder
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)

    async def download_video(self, url, mode="video"):
        ydl_opts = {
            'outtmpl': f'{self.download_folder}/%(title)s.%(ext)s',
            'noplaylist': True,
            'quiet': True,
            'cookiefile': 'cookies.txt', 
            'javascript_runtime': 'node', 
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }

        if mode == "audio":
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # Более мягкий выбор формата: ищем лучшее видео до 720p, но если нет — берем что дают
            ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[ext=m4a]/best[height<=720]/best'
            # Добавляем совместимость
            ydl_opts['merge_output_format'] = 'mp4'

        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(None, lambda: self._extract_and_download(url, ydl_opts))
            return info['filepath']
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            return None

    def _extract_and_download(self, url, opts):
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if opts.get('postprocessors'):
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            return {'filepath': filename}

