from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
import yt_dlp
import subprocess
import os
import requests
import urllib.parse

app = FastAPI(title="OffBeat Backend")

# Enable CORS for frontend requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configurações do OAuth do Google/YouTube (Defina no painel do Render > Environment Variables)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://offbeat-backend-22xy.onrender.com/api/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://offbeat-music.onrender.com")

# User-Agent atualizado para simular navegador real
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

@app.get("/")
def home():
    return {
        "status": "OffBeat Backend Online",
        "oauth_configured": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
    }

@app.get("/api/auth/login")
def login_youtube():
    """Redireciona o usuário para a página de permissões da conta do Google/YouTube."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=500, 
            detail="GOOGLE_CLIENT_ID não está configurado nas variáveis de ambiente do Render."
        )
        
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={urllib.parse.quote(GOOGLE_CLIENT_ID)}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        "&response_type=code"
        "&scope=https://www.googleapis.com/auth/youtube.readonly%20email%20profile"
        "&access_type=offline"
        "&prompt=consent"
    )
    return RedirectResponse(url=google_auth_url)

@app.get("/api/auth/callback")
def auth_callback(code: str = None, error: str = None):
    """Recebe o código de autorização do Google, troca por um Access Token e obtém os dados do perfil."""
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?error={urllib.parse.quote(error)}")
        
    if not code:
        raise HTTPException(status_code=400, detail="Código de autorização não fornecido.")
        
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
        error_detail = token_response.json().get("error_description", "Falha na autenticação do Google")
        return RedirectResponse(url=f"{FRONTEND_URL}?error={urllib.parse.quote(error_detail)}")
        
    tokens = token_response.json()
    access_token = tokens.get("access_token")
    
    # Busca dados básicos do perfil do usuário
    user_info_resp = requests.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user_info = user_info_resp.json() if user_info_resp.status_code == 200 else {}
    
    # Redireciona para o frontend repassando o token e informações do usuário
    name_q = urllib.parse.quote(user_info.get('name', ''))
    pic_q = urllib.parse.quote(user_info.get('picture', ''))
    frontend_redirect_url = f"{FRONTEND_URL}?access_token={access_token}&name={name_q}&picture={pic_q}"
    return RedirectResponse(url=frontend_redirect_url)

@app.get("/api/search")
def search_music(q: str):
    try:
        ydl_opts = {
            'extract_flat': True,
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'force_generic_extractor': False,
            'source_address': '0.0.0.0',  # Força conexão IPv4
            'user_agent': USER_AGENT,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web', 'mweb']
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
        print(f"Erro ao buscar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erro na busca: {str(e)}")

@app.get("/api/stream/{video_id}")
def stream_music(video_id: str):
    try:
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0', # Força conexão IPv4
            'user_agent': USER_AGENT,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'mweb']
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            audio_url = None
            
            # Procura a URL direta do fluxo de áudio
            for f in info.get('formats', []):
                if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_url = f.get('url')
                    break
            
            if not audio_url:
                audio_url = info.get('url')
                
        if not audio_url:
            raise HTTPException(status_code=404, detail="Stream de áudio não encontrado")
            
        def generator():
            # Executa o FFmpeg repassando o fluxo direto para o cliente HTTP
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
