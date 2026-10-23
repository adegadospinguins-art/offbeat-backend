<!-- ... existing code ... -->
# Configurações otimizadas do yt-dlp usando clientes de TV/VR para burlar o bloqueio de bot do YouTube no Render
YDL_OPTIONS_BASE = {
    'quiet': True,
    'no_warnings': True,
    'nocheckcertificate': True,
    'geo_bypass': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'extractor_args': {
        'youtube': {
            'player_client': ['android_vr', 'tv', 'web_creator', 'mweb'],
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
    """Extrai o link direto de áudio do YouTube com bypass de detecção de bot e fallback."""
    
    # Responder de imediato a requisições HEAD enviadas pelo navegador/player
    if request.method == "HEAD":
        return JSONResponse(content={"status": "ok"}, status_code=200)

    url = f"https://www.youtube.com/watch?v={video_id}"
    
    ydl_opts = {
        **YDL_OPTIONS_BASE,
        'format': 'bestaudio/best',
    }
    
    # 1. Tativa via yt-dlp usando cliente Android VR / TV
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = info.get('formats', [])
            audio_url = None
            
            for f in formats:
                if f.get('vcodec') == 'none' and f.get('url'):
                    audio_url = f.get('url')
                    break
            
            if not audio_url and info.get('url'):
                audio_url = info.get('url')

            if not audio_url and formats:
                audio_url = formats[0].get('url')
                
            if audio_url:
                return RedirectResponse(url=audio_url, status_code=307)
    except Exception as err:
        pass  # Fallback abaixo em caso de falha de extração ou bloqueio de IP

    # 2. Fallback via proxy público de áudio (Cobalt/Piped Stream API)
    try:
        piped_url = f"https://pipedapi.kavin.rocks/streams/{video_id}"
        import urllib.request
        import json
        req = urllib.request.Request(piped_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            audio_streams = data.get('audioStreams', [])
            if audio_streams and len(audio_streams) > 0:
                direct_url = audio_streams[0].get('url')
                if direct_url:
                    return RedirectResponse(url=direct_url, status_code=307)
    except Exception as e:
        pass

    raise HTTPException(status_code=500, detail="Não foi possível extrair o fluxo de áudio para este vídeo.")
