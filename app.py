from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading

app = Flask(__name__)
DOWNLOAD_FOLDER = '/tmp/downloads'

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def delete_file_later(filepath, delay=60):
    """מחיקת הקובץ לאחר 60 שניות כדי לפנות מקום בשרת"""
    def _delete():
        import time
        time.sleep(delay)
        if os.path.exists(filepath):
            os.remove(filepath)
    threading.Thread(target=_delete, daemon=True).start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    url = data.get('url')
    if not url:
        return jsonify({'error': 'לא סופק קישור'}), 400

    try:
        filename = str(uuid.uuid4())
        ydl_opts = {
            'outtmpl': f'{DOWNLOAD_FOLDER}/{filename}.%(ext)s',
            'format': 'bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/bestvideo[vcodec^=avc1]+bestaudio/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'quiet': True
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = info.get('ext', 'mp4')
            title = info.get('title', 'video')

            return jsonify({
                'success': True,
                'download_url': f'/get-file/{filename}.{ext}',
                'title': title
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/get-file/<filename>')
def get_file(filename):
    filepath = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(filepath):
        delete_file_later(filepath)  # מחיקה אוטומטית אחרי 60 שניות
        return send_file(filepath, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)
