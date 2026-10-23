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

@app.get("/api/auth/login")
def auth_login(redirect_uri: str = "https://offbeat-backend-22xy.onrender.com/"):
    """
    Redireciona para o login real do Google/YouTube OAuth2.
    Após a autenticação no Google, o usuário é retornado com os dados.
    """
    from fastapi.responses import RedirectResponse
    import urllib.parse

    # 1. SUBSTITUA PELO SEU CLIENT ID DO GOOGLE CLOUD CONSOLE
    CLIENT_ID = "SEU_CLIENT_ID_DO_GOOGLE_CLOUD.apps.googleusercontent.com"
    
    # Se ainda não configurou o Google OAuth Console, mantemos o parâmetro dinâmico para os testes:
    if CLIENT_ID.startswith("SEU_CLIENT_ID"):
        # Retorno de teste utilizando o redirect_uri informado pelo frontend
        target_url = f"{redirect_uri}?access_token=demo_token&name=Usuario+OffBeat&picture=https://i.pravatar.cc/150?img=68"
        return RedirectResponse(url=target_url)

    # 2. FLUXO REAL DO OAUTH2 DO GOOGLE / YOUTUBE:
    google_auth_endpoint = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "token",
        "scope": "https://www.googleapis.com/auth/youtube.readonly https://www.googleapis.com/auth/userinfo.profile",
        "include_granted_scopes": "true",
        "state": "offbeat_auth"
    }
    
    auth_url = f"{google_auth_endpoint}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url)

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
