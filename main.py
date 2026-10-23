from fastapi import FastAPI, HTTPException, Query, Request
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

# Configurações do yt-dlp simulando clientes mobile (Android/iOS) para burlar o bloqueio de Bot no Render
YDL_OPTIONS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'ios', 'web'],
            'skip': ['hls', 'dash']
        }
    }
}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "OffBeat Backend online!"}

@app.get("/api/search")
def search_youtube(q: str = Query(..., description="Termo de pesquisa ou URL do YouTube")):
    """Pesquisa faixas no YouTube e retorna metadados e IDs."""
    ydl_opts = {
        **YDL_OPTIONS_BASE,
        'format': 'bestaudio/best',
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

@app.api_route("/api/stream/{video_id}", methods=["GET", "HEAD"])
def stream_audio(video_id: str, request: Request):
    """Extrai o link direto de áudio do YouTube configurado para evitar detecção de bot."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        **YDL_OPTIONS_BASE,
        'format': 'bestaudio/best',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Encontra o melhor formato apenas de áudio
            formats = info.get('formats', [])
            audio_url = None
            
            # 1. Procura primeiro formatos apenas de áudio
            for f in formats:
                if f.get('vcodec') == 'none' and f.get('url'):
                    audio_url = f.get('url')
                    break
            
            # 2. Fallback para a URL direta se encontrada no topo
            if not audio_url and info.get('url'):
                audio_url = info.get('url')

            # 3. Fallback genérico para o primeiro formato disponível
            if not audio_url and formats:
                audio_url = formats[0].get('url')
                
            if not audio_url:
                raise HTTPException(status_code=404, detail="Não foi possível extrair o áudio deste vídeo.")
                
            # Se for requisição HEAD de pré-checagem do navegador
            if request.method == "HEAD":
                return JSONResponse(content={"status": "ok"}, status_code=200)

            # Redireciona diretamente para o fluxo direto de áudio extraído
            return RedirectResponse(url=audio_url, status_code=307)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
