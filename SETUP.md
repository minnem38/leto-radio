# Leto Radio - Setup Guide

## Pushing to GitHub

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/YOURUSERNAME/leto-radio.git
git push -u origin main
```

The `.gitignore` ensures your `.env` is never committed — your Discord token stays safe.

---

## Deploying via Portainer Stack (recommended)

1. In Portainer go to **Stacks → Add Stack**
2. Choose **Repository** and paste your GitHub repo URL
3. Set the compose file path to `docker-compose.yml`
4. Scroll down to **Environment variables** and add:

| Name | Value |
|------|-------|
| `DISCORD_TOKEN` | your bot token |
| `RADIO_CHANNEL_NAME` | `leto-radio` |
| `MAX_QUEUE_SIZE` | `20` |

5. Click **Deploy the stack**

Portainer will pull from GitHub and build the images. When you push updates to GitHub, just hit **Pull and redeploy** in Portainer — no SSH needed.

---

## Deploying manually (alternative)

```bash
# On your Pi
git clone https://github.com/YOURUSERNAME/leto-radio.git
cd leto-radio
cp .env.example .env
nano .env   # fill in your DISCORD_TOKEN
docker compose up -d
```

---

## Creating your Discord bot

1. Go to https://discord.com/developers/applications
2. New Application → name it "Leto Radio"
3. Bot tab → Add Bot → copy the token
4. Under **Privileged Gateway Intents** enable **Message Content Intent**
5. OAuth2 → URL Generator → select `bot` scope
6. Bot permissions: Read Messages, Send Messages, Read Message History
7. Copy the generated URL and invite the bot to your server

---

## Nginx Proxy Manager

Add a new Proxy Host:
- **Domain:** `radio.yourdomain.com`
- **Forward Hostname/IP:** your Pi's local IP
- **Forward Port:** `8765`
- Enable SSL with Let's Encrypt

---

## Etched disc URL in Minecraft

```
https://radio.yourdomain.com/stream
```

---

## Useful commands

```bash
docker compose logs -f                  # view all logs
docker compose logs -f bot              # just bot logs
docker compose restart bot              # restart the bot
docker compose exec bot yt-dlp -U      # update yt-dlp
docker compose down                     # stop everything
```

---

## Discord commands (in #leto-radio)

| Command | What it does |
|---------|-------------|
| Paste any YouTube/SoundCloud/Bandcamp link | Queues the song |
| `!queue` | Shows what's coming up |
| `!np` | Shows what's playing now |
| `!help` | Shows all commands |
