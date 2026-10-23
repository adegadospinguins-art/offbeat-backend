from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
import yt_dlp

app = FastAPI(title="OffBeat Music Proxy API")

# Permite que o seu aplicativo Web/PWA acesse a API de qualquer lugar
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "OffBeat Backend online!"}

@app.get("/api/search")
def search_youtube(q: str = Query(..., description="Termo de pesquisa ou URL do YouTube")):
    """Pesquisa faixas no YouTube e retorna metadados e IDs."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',
        'default_search': 'ytsearch8',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(q, download=False)
            results = []
            
            entries = info.get('entries', [info]) if 'entries' in info else [info]
            for entry in entries:
                if not entry:
                    continue
                results.append({
                    "id": entry.get("id"),
                    "title": entry.get("title", "Música sem título"),
                    "artist": entry.get("uploader", "YouTube"),
                    "duration": entry.get("duration", 0),
                    "thumbnail": f"https://i.ytimg.com/vi/{entry.get('id')}/hqdefault.jpg",
                    "url": f"https://www.youtube.com/watch?v={entry.get('id')}"
                })
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/{video_id}")
def stream_audio(video_id: str):
    """Extrai o link direto de áudio com streaming ativado."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Encontra o melhor formato apenas de áudio
            formats = info.get('formats', [])
            audio_url = None
            
            for f in formats:
                if f.get('vcodec') == 'none' and f.get('url'):
                    audio_url = f.get('url')
                    break
            
            if not audio_url and formats:
                audio_url = formats[0].get('url')
                
            if not audio_url:
                raise HTTPException(status_code=404, detail="Não foi possível extrair o áudio deste vídeo.")
                
            # Redireciona diretamente para o fluxo de áudio
            return RedirectResponse(url=audio_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
