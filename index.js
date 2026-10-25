const express = require('express');
const cors = require('cors');
const ytdl = require('@distube/ytdl-core');

const app = express();
app.use(cors());

// 1. ENDPOINT DE BUSCA
app.get('/api/search', async (req, res) => {
    const query = req.query.q || 'sertanejo';

    try {
        const searchUrl = `https://invidious.privacydev.net/api/v1/search?q=${encodeURIComponent(query)}&type=video`;
        const response = await fetch(searchUrl);

        if (!response.ok) throw new Error('Falha ao consultar API');

        const data = await response.json();

        const tracks = data.slice(0, 15).map(item => ({
            id: item.videoId,
            title: item.title,
            artist: item.author || 'Artista',
            duration: item.lengthSeconds,
            cover: item.videoThumbnails && item.videoThumbnails.length > 0 
                ? item.videoThumbnails.find(t => t.quality === 'high' || t.quality === 'medium')?.url || item.videoThumbnails[0].url
                : `https://i.ytimg.com/vi/${item.videoId}/hqdefault.jpg`
        }));

        res.json(tracks);
    } catch (error) {
        try {
            const fallbackUrl = `https://inv.tux.pizza/api/v1/search?q=${encodeURIComponent(query)}&type=video`;
            const fbRes = await fetch(fallbackUrl);
            const fbData = await fbRes.json();

            const tracks = fbData.slice(0, 15).map(item => ({
                id: item.videoId,
                title: item.title,
                artist: item.author || 'Artista',
                duration: item.lengthSeconds,
                cover: `https://i.ytimg.com/vi/${item.videoId}/hqdefault.jpg`
            }));

            res.json(tracks);
        } catch (fbErr) {
            res.status(500).json({ error: 'Erro ao buscar músicas' });
        }
    }
});

// 2. ENDPOINT DE STREAM
app.get('/api/stream', async (req, res) => {
    const videoId = req.query.id;
    if (!videoId) return res.status(400).json({ error: 'ID necessário' });

    try {
        const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
        const info = await ytdl.getInfo(videoUrl);
        const format = ytdl.chooseFormat(info.formats, { filter: 'audioonly', quality: 'highestaudio' });

        if (format && format.url) {
            res.json({ streamUrl: format.url });
        } else {
            res.status(404).json({ error: 'Áudio não encontrado' });
        }
    } catch (error) {
        res.status(500).json({ error: 'Erro ao extrair áudio' });
    }
});

// 3. ENDPOINT DE DOWNLOAD
app.get('/api/download', async (req, res) => {
    const videoId = req.query.id;
    if (!videoId) return res.status(400).json({ error: 'ID necessário' });

    try {
        const videoUrl = `https://www.youtube.com/watch?v=${videoId}`;
        res.setHeader('Content-Disposition', `attachment; filename="${videoId}.mp3"`);
        res.setHeader('Content-Type', 'audio/mpeg');

        ytdl(videoUrl, { filter: 'audioonly', quality: 'highestaudio' }).pipe(res);
    } catch (error) {
        res.status(500).send('Erro ao realizar download');
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Servidor rodando na porta ${PORT}`));
