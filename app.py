from flask import Flask, request, jsonify, send_file
import yt_dlp
import os
import threading

app = Flask(__name__)

# İndirme klasörü
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# İlerleme durumu
progress_data = {
    "progress": 0,
    "status": "idle"
}
cancel_download = False

# Ana sayfa rotası
@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>YouTube Video Downloader</title>
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600&display=swap" rel="stylesheet">
        <style>
            body {
                font-family: 'Poppins', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
                background-color: #f0f2f5;
                color: #333;
            }
            .container {
                background: #ffffff;
                padding: 40px;
                border-radius: 8px;
                box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
                text-align: center;
                width: 400px;
                max-width: 100%;
            }
            h2 {
                color: #007bff;
                font-size: 28px;
                margin-bottom: 20px;
            }
            input[type="url"] {
                width: 100%;
                padding: 12px 20px;
                border: 1px solid #ccc;
                border-radius: 5px;
                margin-bottom: 20px;
                font-size: 16px;
                color: #333;
            }
            button {
                background-color: #007bff;
                color: white;
                padding: 12px 20px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                transition: background-color 0.3s ease;
                width: 100%;
            }
            button:hover {
                background-color: #0056b3;
            }
            #progress-bar {
                width: 100%;
                background-color: #e9ecef;
                border-radius: 5px;
                margin-top: 20px;
                height: 15px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                display: none;
                margin-top: 30px;
            }
            #progress-bar span {
                display: block;
                height: 100%;
                background-color: #4caf50;
                border-radius: 5px;
                text-align: center;
                color: white;
                font-weight: bold;
                transition: width 0.4s ease-in-out;
            }
            .message {
                margin-top: 15px;
                font-size: 14px;
                color: #28a745;
                font-weight: 600;
            }
            .error {
                color: #dc3545;
                font-weight: 600;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #007bff;
                border-radius: 50%;
                width: 50px;
                height: 50px;
                animation: spin 1s linear infinite;
                margin: 20px auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>YouTube Video Downloader</h2>
            <input type="url" id="video-url" placeholder="Enter YouTube URL" required>
            <button id="download-btn">Download</button>
            <button id="cancel-btn" style="display:none;margin-top:10px;">Cancel Download</button>
            <p id="message" class="message"></p>
            <div id="progress-bar">
                <span id="progress-bar-fill"></span>
            </div>
            <div id="spinner" class="spinner" style="display:none;"></div>
        </div>

        <script>
            const downloadButton = document.getElementById('download-btn');
            const cancelButton = document.getElementById('cancel-btn');
            const message = document.getElementById('message');
            const progressBarFill = document.getElementById('progress-bar-fill');
            const progressBar = document.getElementById('progress-bar');
            const spinner = document.getElementById('spinner');
            let progressInterval;
            let downloadProcess = null;

            downloadButton.addEventListener('click', async () => {
                const videoUrl = document.getElementById('video-url').value;

                if (!videoUrl) {
                    message.textContent = 'Please enter a valid URL.';
                    message.classList.add('error');
                    return;
                }

                message.textContent = '';
                progressBar.style.display = 'block';
                spinner.style.display = 'block';
                cancelButton.style.display = 'inline-block';

                try {
                    const response = await fetch('/download', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ url: videoUrl }),
                    });

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || 'Unknown error occurred.');
                    }

                    const result = await response.json();
                    const fileName = result.file_name;

                    // Progress intervalini başlat
                    progressInterval = setInterval(async () => {
                        const progressResponse = await fetch('/progress');
                        const progressData = await progressResponse.json();
                        const progress = progressData.progress;

                        // Progres bar'ı güncelle
                        progressBarFill.style.width = `${progress}%`;

                        if (progress >= 100) {
                            clearInterval(progressInterval);
                            message.textContent = 'Download complete!';
                            message.classList.remove('error');
                            message.classList.add('message');
                            spinner.style.display = 'none';
                            cancelButton.style.display = 'none';
                        }
                    }, 1000);

                    const fileResponse = await fetch(`/download-file/${fileName}`);
                    const blob = await fileResponse.blob();

                    const link = document.createElement('a');
                    link.href = window.URL.createObjectURL(blob);
                    link.download = fileName;
                    link.click();

                } catch (error) {
                    message.textContent = `Error: ${error.message}`;
                    message.classList.add('error');
                    spinner.style.display = 'none';
                    cancelButton.style.display = 'none';
                }
            });

            cancelButton.addEventListener('click', async () => {
                const response = await fetch('/cancel', { method: 'POST' });

                if (response.ok) {
                    message.textContent = 'Download canceled.';
                    message.classList.add('error');
                    progressBar.style.display = 'none';
                    spinner.style.display = 'none';
                    cancelButton.style.display = 'none';
                    clearInterval(progressInterval);
                }
            });
        </script>
    </body>
    </html>
    '''

# Video indirme rotası
@app.route('/download', methods=['POST'])
def download_video():
    global cancel_download
    cancel_download = False
    data = request.json
    if not data or 'url' not in data:
        return jsonify({"error": "Video URL is required"}), 400

    url = data['url']
    ydl_opts = {
        'format': 'bestvideo+bestaudio/best',
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'merge_output_format': 'mp4',
        'progress_hooks': [progress_hook],
    }

    def download_task():
        global cancel_download
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_name = f"{info['title']}.mp4"
                return jsonify({"file_name": file_name})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    threading.Thread(target=download_task).start()

    return jsonify({"message": "Download started"}), 202

# İlerleme bilgisini al
def progress_hook(d):
    global cancel_download
    if cancel_download:
        d['status'] = 'canceled'

    if d['status'] == 'downloading':
        total_size = d.get('total_bytes', 1)
        downloaded = d.get('downloaded_bytes', 0)
        progress = int(downloaded / total_size * 100) if total_size else 0
        progress_data["progress"] = progress
        progress_data["status"] = "downloading"

# İlerleme bilgisini sağla
@app.route('/progress')
def get_progress():
    return jsonify(progress_data)

# İptal işlemi
@app.route('/cancel', methods=['POST'])
def cancel():
    global cancel_download
    cancel_download = True
    return jsonify({"message": "Download canceled."})

# İndirilen dosyayı istemciye gönderme
@app.route('/download-file/<file_name>')
def download_file(file_name):
    file_path = os.path.join(DOWNLOAD_FOLDER, file_name)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(file_path, as_attachment=True)
    
if __name__ == "__main__":
    app.run(debug=True, host='127.0.0.1', port=5001)
