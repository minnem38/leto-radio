# 🎵 Leto Radio Bot

A Discord bot that converts YouTube, SoundCloud, and direct audio links into streamable URLs for Minecraft radio mods. Files auto-delete after 1 hour.

**GitHub:** [minnem38/leto-radio](https://github.com/minnem38/leto-radio)  
**Image:** `ghcr.io/minnem38/leto-radio:latest`

---

## How it works

1. Paste a YouTube / SoundCloud / MP3 link in your Discord channel
2. The bot downloads and converts it to MP3 via `yt-dlp` + `ffmpeg`
3. Bot replies with a direct stream URL
4. Paste that URL into your Minecraft radio mod
5. File auto-deletes after 1 hour

```
Discord: https://youtu.be/dQw4w9WgXcQ
    ↓
Bot:     https://radio.yourdomain.com/audio/abc123.mp3
    ↓
Minecraft radio mod → 🎶
```

---

## Supported sources

| Source | Example |
|---|---|
| YouTube | `https://youtube.com/watch?v=...` |
| YouTube short | `https://youtu.be/...` |
| SoundCloud | `https://soundcloud.com/artist/track` |
| Direct MP3/OGG | `https://example.com/song.mp3` |
| Bandcamp | `https://artist.bandcamp.com/track/...` |
| Any yt-dlp source | Most public audio |

## Compatible Minecraft mods

- Simple Voice Chat (radio addon)
- Phonograph
- Immersive Engineering Radio
- Valhelsia Radio
- Any mod accepting a direct HTTP audio URL

---

## Setup

### 1. Create a Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → name it
3. **Bot** → **Add Bot** → enable **Message Content Intent**
4. Copy the **Token**
5. **OAuth2 → URL Generator**: scopes `bot`, permissions: Read Messages, Send Messages, Embed Links
6. Open the URL and invite the bot to your server

### 2. Get your channel ID

Enable **Developer Mode** in Discord (Settings → Advanced), then right-click your channel → **Copy Channel ID**.

### 3. Push to GitHub & let Actions build the image

```bash
git clone https://github.com/minnem38/leto-radio.git
cd leto-radio
# make your changes, then:
git push origin main
```

GitHub Actions will automatically build and push `ghcr.io/minnem38/leto-radio:latest` (arm64 + amd64) on every push to `main`.

### 4a. Deploy via Portainer — Repository method (recommended)

1. Portainer → **Stacks** → **Add stack** → **Repository**
2. Repository URL: `https://github.com/minnem38/leto-radio`
3. Compose path: `docker-compose.yml`
4. Add environment variables:
   - `DISCORD_TOKEN`
   - `DISCORD_CHANNEL_ID`
   - `PUBLIC_URL`
5. **Deploy the stack**

### 4b. Deploy via Portainer — Web editor

1. Portainer → **Stacks** → **Add stack** → **Web editor**
2. Paste the contents of `docker-compose.portainer.yml`
3. Add environment variables in the env section below the editor
4. **Deploy the stack**

### 4c. Deploy via CLI

```bash
cp .env.example .env
nano .env   # fill in your values
docker compose up -d
```

---

## Nginx Proxy Manager setup (recommended)

Point a subdomain like `radio.yourdomain.nl` at the fileserver:

- **Forward hostname:** `leto-radio-fileserver`
- **Forward port:** `80`
- Enable SSL (Let's Encrypt)
- Set `PUBLIC_URL=https://radio.yourdomain.nl` in your env

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Bot token |
| `DISCORD_CHANNEL_ID` | ✅ | — | Channel to watch |
| `PUBLIC_URL` | ✅ | — | Public URL of the file server |
| `FILE_TTL_SECONDS` | ❌ | `3600` | Seconds until files are deleted |
| `FILESERVER_PORT` | ❌ | `8765` | Local port for file server |

---

## Project structure

```
leto-radio/
├── bot/
│   ├── bot.py              # Discord bot
│   ├── requirements.txt
│   └── Dockerfile
├── nginx/
│   └── default.conf        # Audio file server
├── .github/
│   └── workflows/
│       └── docker.yml      # Auto-build arm64 image on push
├── docker-compose.yml          # CLI / Portainer Repository
├── docker-compose.portainer.yml  # Portainer Web editor
├── .env.example
├── .gitignore
└── README.md
```

---

## Updating yt-dlp

yt-dlp updates frequently. If downloads break, trigger a rebuild:

```bash
# CLI
docker compose build --no-cache bot && docker compose up -d

# GitHub Actions: push any commit to main → auto-rebuilds
```
