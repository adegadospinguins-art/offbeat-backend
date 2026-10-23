from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import subprocess

app = FastAPI(title="OffBeat Backend")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# User-Agent string to emulate a legitimate desktop web browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

@app.get("/")
def home():
    return {"status": "OffBeat Backend Online"}

@app.get("/api/search")
def search_music(q: str):
    try:
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'user_agent': USER_AGENT,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(q, download=False)
            results = []
            
            entries = info.get('entries', [info]) if 'entries' in info else [info]
            for entry in entries[:15]:
                if entry:
                    video_id = entry.get('id') or entry.get('url')
                    if video_id:
                        results.append({
                            "id": video_id,
                            "title": entry.get('title', 'Título Desconhecido'),
                            "artist": entry.get('uploader') or entry.get('channel') or 'Artista Desconhecido',
                            "thumbnail": entry.get('thumbnail') or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                        })
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/{video_id}")
def stream_music(video_id: str):
    try:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'user_agent': USER_AGENT,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = None
            
            # Find direct audio stream URL
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    break
            
            if not audio_url:
                audio_url = info.get('url')
                
        if not audio_url:
            raise HTTPException(status_code=404, detail="Stream não encontrado")
            
        def generator():
            # Pass User-Agent and headers directly to FFmpeg so YouTube won't block or close the connection
            ffmpeg_cmd = [
                'ffmpeg',
                '-headers', f'User-Agent: {USER_AGENT}\r\n',
                '-i', audio_url,
                '-f', 'mp3',
                '-acodec', 'libmp3lame',
                '-ab', '128k',
                '-'
            ]
            
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            try:
                while True:
                    data = process.stdout.read(8192)
                    if not data:
                        break
                    yield data
            finally:
                process.kill()
                
        return StreamingResponse(
            generator(),
            media_type="audio/mpeg",
            headers={
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
