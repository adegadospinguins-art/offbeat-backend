from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import subprocess

app = FastAPI(title="OffBeat Backend")

# Habilita o CORS para permitir requisições de qualquer frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
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
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}}
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = None
            
            # Procura o link direto do stream de áudio
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    break
            
            if not audio_url:
                audio_url = info.get('url')
                
        if not audio_url:
            raise HTTPException(status_code=404, detail="Stream não encontrado")
            
        def generator():
            process = subprocess.Popen(
                ['ffmpeg', '-i', audio_url, '-f', 'mp3', '-'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            while True:
                data = process.stdout.read(4096)
                if not data:
                    break
                yield data
                
        return StreamingResponse(generator(), media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
