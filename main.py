from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
import yt_dlp
import subprocess
import os
import requests

app = FastAPI(title="OffBeat Backend")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações do OAuth do Google/YouTube (Defina essas variáveis no seu ambiente ou no Render)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "SEU_CLIENT_ID_AQUI")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "SEU_CLIENT_SECRET_AQUI")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://offbeat-backend-22xy.onrender.com/api/auth/callback")

# User-Agent string to emulate a legitimate desktop web browser
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

@app.get("/")
def home():
    return {"status": "OffBeat Backend Online"}

@app.get("/api/auth/login")
def login_youtube():
    """Redireciona o usuário para a página de permissões da conta do Google/YouTube."""
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/youtube.readonly%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    return RedirectResponse(url=google_auth_url)

@app.get("/api/auth/callback")
def auth_callback(code: str):
    """Recebe o código de autorização do Google, troca por um Access Token e obtém os dados do perfil."""
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    token_response = requests.post(token_url, data=data)
    if token_response.status_code != 200:
        raise HTTPException(status_code=400, detail="Falha na autenticação do Google")
        
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    
    # Busca dados básicos do perfil do usuário
    user_info_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_info = user_info_resp.json() if user_info_resp.status_code == 200 else {}
    
    # Redireciona para o frontend repassando o token e informações do usuário via parâmetros de URL
    frontend_redirect_url = f"https://offbeat-music.onrender.com?access_token={access_token}&name={user_info.get('name', '')}&picture={user_info.get('picture', '')}"
    return RedirectResponse(url=frontend_redirect_url)

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
