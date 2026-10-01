from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading
import shutil
import tempfile
import sys

# הפעלת ffmpeg מובנה לכל פלטפורמה (ענן / שרת / ווינדוס)
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except Exception as e:
    print(f"static_ffmpeg init info: {e}", file=sys.stderr)

app = Flask(__name__)
DOWNLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'video_downloads')

if not os.path.exists(DOWNLOAD_FOLDER):
    try:
        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    except Exception:
        pass

def get_ffmpeg_path():
    path = shutil.which('ffmpeg')
    if path:
        return path
    win_default = r'C:\Users\97252\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin'
    if os.path.exists(win_default):
        return win_default
    return None

def delete_file_later(filepath, delay=120):
    """מחיקת הקובץ לאחר 2 דקות כדי לפנות מקום בשרת"""
    def _delete():
        import time
        time.sleep(delay)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
    threading.Thread(target=_delete, daemon=True).start()

@app.errorhandler(Exception)
def handle_unexpected_error(e):
    return jsonify({'error': f'שגיאת שרת פנימית: {str(e)}'}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    download_type = data.get('type', 'video')
    quality = data.get('quality', 'best')

    if not url:
        return jsonify({'error': 'אנא הכנס קישור תקין'}), 400

    ffmpeg_path = get_ffmpeg_path()
    filename = str(uuid.uuid4())

    try:
        common_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'socket_timeout': 60,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios', 'tv', 'mweb', 'web']
                }
            }
        }

        if ffmpeg_path:
            common_opts['ffmpeg_location'] = ffmpeg_path

        if download_type == 'audio':
            audio_quality = quality if quality in ['128', '192', '320'] else '192'
            ydl_opts = {
                **common_opts,
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': audio_quality,
                }],
            }
        else:
            if quality == '1080':
                fmt = 'bestvideo[height<=1080][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/bestvideo+bestaudio/best'
            elif quality == '720':
                fmt = 'bestvideo[height<=720][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/bestvideo+bestaudio/best'
            elif quality == '480':
                fmt = 'bestvideo[height<=480][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480]/bestvideo+bestaudio/best'
            elif quality == '360':
                fmt = 'bestvideo[height<=360][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/bestvideo+bestaudio/best'
            else:
                fmt = 'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc1]+bestaudio/bestvideo+bestaudio/best[ext=mp4]/best'

            ydl_opts = {
                **common_opts,
                'format': fmt,
                'merge_output_format': 'mp4',
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'media')

        matching_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(filename)]
        if not matching_files:
            return jsonify({'error': 'הקובץ לא נמצא בשרת לאחר ההורדה'}), 500

        actual_filename = matching_files[0]
        ext = os.path.splitext(actual_filename)[1].lstrip('.')

        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
        if not safe_title:
            safe_title = 'download'

        return jsonify({
            'success': True,
            'download_url': f'/get-file/{actual_filename}',
            'title': f'{safe_title}.{ext}'
        })

    except Exception as e:
        err_msg = str(e)
        if "Sign in to confirm you're not a bot" in err_msg or "bot" in err_msg.lower():
            friendly_err = "יוטיוב חסם זמנית את ההורדה משרת זה (זיהוי בוטים). נסה שוב בעוד מספר רגעים."
        elif "Private video" in err_msg:
            friendly_err = "הסרטון הוא פרטי ולא ניתן להורידו."
        elif "Video unavailable" in err_msg:
            friendly_err = "הסרטון אינו זמין או הוסר."
        else:
            friendly_err = err_msg

        return jsonify({'error': friendly_err}), 400

@app.route('/get-file/<filename>')
def get_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        delete_file_later(filepath)
        return send_file(filepath, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
