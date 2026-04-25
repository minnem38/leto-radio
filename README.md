# 🎵 Minecraft Radio Bot

A Discord bot that converts YouTube, SoundCloud, and direct audio links into streamable URLs for Minecraft radio mods. Files auto-delete after 1 hour.

## How it works

1. Someone pastes a YouTube/SoundCloud/MP3 link in your Discord channel
2. The bot downloads and converts it to MP3 using `yt-dlp` + `ffmpeg`
3. The bot replies with a direct streaming URL
4. You paste that URL into your Minecraft radio mod
5. After 1 hour, the file is automatically deleted

```
Discord message: https://youtu.be/dQw4w9WgXcQ
         ↓
Bot reply: https://radio.yourdomain.com/audio/abc123def.mp3
         ↓
Paste into Minecraft radio mod → profit 🎶
```

## Compatible Minecraft mods

- **Simple Voice Chat** (radio addon)
- **Phonograph**
- **Immersive Engineering** (radio)
- **Valhelsia Radio**
- Any mod that accepts a direct HTTP audio URL

## Supported link types

| Source | Example |
|---|---|
| YouTube | `https://youtube.com/watch?v=...` |
| YouTube short | `https://youtu.be/...` |
| SoundCloud | `https://soundcloud.com/artist/track` |
| Direct MP3 | `https://example.com/song.mp3` |
| Bandcamp | `https://artist.bandcamp.com/track/...` |
| Other | Anything yt-dlp supports |

---

## Setup

### Prerequisites

- A server or Raspberry Pi running Docker + Docker Compose
- Portainer (optional, but recommended for easy management)
- A domain name pointed at your server (recommended) **or** a static public IP
- Nginx Proxy Manager (optional, for HTTPS)

### 1. Create a Discord bot

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** → give it a name
3. Go to **Bot** → click **Add Bot**
4. Under **Privileged Gateway Intents**, enable **Message Content Intent**
5. Copy the **Token** (you'll need it in `.env`)
6. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot permissions: `Read Messages/View Channels`, `Send Messages`, `Embed Links`, `Read Message History`
7. Open the generated URL and invite the bot to your server

### 2. Get your channel ID

1. In Discord, enable **Developer Mode** (Settings → Advanced → Developer Mode)
2. Right-click the channel → **Copy Channel ID**

### 3. Clone and configure

```bash
git clone https://github.com/YOUR_USERNAME/minecraft-radio-bot.git
cd minecraft-radio-bot

cp .env.example .env
nano .env   # fill in your values
```

### 4a. Deploy with Portainer

1. In Portainer, go to **Stacks** → **Add stack**
2. Choose **Repository** and paste your GitHub repo URL  
   *Or* choose **Upload** and paste the `docker-compose.yml` contents
3. Add your environment variables in the **Environment variables** section:
   - `DISCORD_TOKEN`
   - `DISCORD_CHANNEL_ID`
   - `PUBLIC_URL`
4. Click **Deploy the stack**

### 4b. Deploy with Docker Compose (CLI)

```bash
docker compose up -d --build
```

Check logs:
```bash
docker compose logs -f bot
```

### 5. Set up a reverse proxy (recommended)

If you're using **Nginx Proxy Manager**:

1. Add a new **Proxy Host**
2. Domain: `radio.yourdomain.com`
3. Forward hostname: `radio-fileserver`
4. Forward port: `80`
5. Enable SSL with Let's Encrypt
6. Set `PUBLIC_URL=https://radio.yourdomain.com` in your `.env`

---

## Configuration

All config is via environment variables (`.env` file):

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Your bot token |
| `DISCORD_CHANNEL_ID` | ✅ | — | Channel to monitor |
| `PUBLIC_URL` | ✅ | — | Public URL of your file server |
| `FILE_TTL_SECONDS` | ❌ | `3600` | Seconds before files are deleted |
| `FILESERVER_PORT` | ❌ | `8765` | Local port for the file server |

---

## Project structure

```
minecraft-radio-bot/
├── bot/
│   ├── bot.py              # Discord bot logic
│   ├── requirements.txt
│   └── Dockerfile
├── nginx/
│   └── default.conf        # Audio file server config
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## Security notes

- The file server only serves files under `/audio/` — nothing else is accessible
- `.env` is in `.gitignore` — never commit your bot token
- Files are served without authentication; anyone with the URL can stream the audio (same as any radio stream)
- `CORS` is enabled on the file server so Minecraft can reach it from any context

## Troubleshooting

**Bot doesn't respond to links**
- Check that Message Content Intent is enabled in the Discord developer portal
- Make sure the bot is in the right channel (`DISCORD_CHANNEL_ID`)

**"Failed to download audio"**
- The link may be private, region-locked, or age-restricted
- `yt-dlp` is regularly updated; rebuild the container to get the latest version: `docker compose build --no-cache bot`

**Minecraft can't connect to the stream**
- Make sure `PUBLIC_URL` is reachable from the internet
- If using HTTP (not HTTPS), some mods may block it — set up SSL via Nginx Proxy Manager
- Test the URL in a browser first: it should prompt a download of the MP3

**Rebuilding after a yt-dlp update**
```bash
docker compose build --no-cache bot
docker compose up -d
```
