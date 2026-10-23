from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import subprocess

app = FastAPI(title="OffBeat Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

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
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'user_agent': USER_AGENT,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'mweb']
                }
            }
        }
        
        query_target = q if q.startswith('http') else f"ytsearch15:{q}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query_target, download=False)
            results = []
            
            entries = info.get('entries', [info]) if info and 'entries' in info else ([info] if info else [])
            for entry in entries:
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
        print(f"Erro na busca: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")

@app.get("/api/stream/{video_id}")
def stream_music(video_id: str):
    try:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0',
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
            
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    break
            
            if not audio_url:
                audio_url = info.get('url')
                
        if not audio_url:
            raise HTTPException(status_code=404, detail="Stream de áudio não encontrado")
            
        def generator():
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
                stderr=subprocess.DEVNULL
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
        print(f"Erro no streaming: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro ao obter áudio: {str(e)}")
