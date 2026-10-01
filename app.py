from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading
import shutil
import tempfile

app = Flask(__name__)
DOWNLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'video_downloads')

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# איתור ffmpeg במערכת (ווינדוס או לינוקס/ענן)
def get_ffmpeg_path():
    path = shutil.which('ffmpeg')
    if path:
        return path
    win_default = r'C:\Users\97252\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin'
    if os.path.exists(win_default):
        return win_default
    return None

def delete_file_later(filepath, delay=90):
    """מחיקת הקובץ לאחר 90 שניות כדי לפנות מקום בשרת"""
    def _delete():
        import time
        time.sleep(delay)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    threading.Thread(target=_delete, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.json or {}
    url = data.get('url', '').strip()
    download_type = data.get('type', 'video')  # video או audio
    quality = data.get('quality', 'best')      # best, 1080, 720, 480, 360, 320, 192, 128

    if not url:
        return jsonify({'error': 'אנא הכנס קישור תקין'}), 400

    ffmpeg_path = get_ffmpeg_path()
    filename = str(uuid.uuid4())

    try:
        if download_type == 'audio':
            # הורדת שמע בלבד והמרה ל-MP3
            audio_quality = quality if quality in ['128', '192', '320'] else '192'
            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_quality,
                }],
                'quiet': True,
            }
        else:
            # הורדת וידאו בפורמט MP4 (H.264)
            if quality == '1080':
                fmt = 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
            elif quality == '720':
                fmt = 'bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best'
            elif quality == '480':
                fmt = 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/best'
            elif quality == '360':
                fmt = 'bestvideo[height<=360][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best'
            else:
                fmt = 'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc1]+bestaudio/best[ext=mp4]/best'

            ydl_opts = {
                'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
                'format': fmt,
                'merge_output_format': 'mp4',
                'quiet': True,
            }

        if ffmpeg_path:
            ydl_opts['ffmpeg_location'] = ffmpeg_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'media')

        # איתור הקובץ שנוצר בתיקייה
        matching_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(filename)]
        if not matching_files:
            return jsonify({'error': 'הקובץ לא נוצר כראוי'}), 500

        actual_filename = matching_files[0]
        ext = os.path.splitext(actual_filename)[1].lstrip('.')

        # ניקוי שם הקובץ מתווים לא חוקיים להורדה
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        if not safe_title:
            safe_title = 'download'

        return jsonify({
            'success': True,
            'download_url': f'/get-file/{actual_filename}',
            'title': f'{safe_title}.{ext}'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get-file/<filename>')
def get_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        delete_file_later(filepath)
        return send_file(filepath, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
