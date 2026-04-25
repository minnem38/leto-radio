import os
import re
import uuid
import asyncio
import logging
import aiohttp
import aiofiles
import discord
from discord.ext import commands
from pathlib import Path
import yt_dlp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ── Config from env ────────────────────────────────────────────────────────────
TOKEN       = os.environ["DISCORD_TOKEN"]
CHANNEL_ID  = int(os.environ["DISCORD_CHANNEL_ID"])
PUBLIC_URL  = os.environ["PUBLIC_URL"].rstrip("/")
FILE_TTL    = int(os.environ.get("FILE_TTL_SECONDS", 3600))
AUDIO_DIR   = Path(os.environ.get("AUDIO_DIR", "/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ── URL pattern ────────────────────────────────────────────────────────────────
URL_RE = re.compile(
    r"https?://"
    r"(?:www\.)?"
    r"(?:"
    r"youtube\.com/watch\?[^\s]*v=[\w-]+"
    r"|youtu\.be/[\w-]+"
    r"|soundcloud\.com/[\w/-]+"
    r"|open\.spotify\.com/track/[\w]+"
    r"|[\w.-]+\.bandcamp\.com/track/[\w/-]+"
    r"|[\w.-]+\.(?:mp3|ogg|flac|wav)(?:\?[^\s]*)?"
    r"|[\w.-]+/[\w/.-]+\.(?:mp3|ogg|flac|wav)(?:\?[^\s]*)?"
    r")",
    re.IGNORECASE,
)

# ── yt-dlp options ─────────────────────────────────────────────────────────────
def ydl_opts(output_path: str) -> dict:
    return {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
    }

# ── Bot ────────────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def schedule_deletion(path: Path, delay: int):
    await asyncio.sleep(delay)
    try:
        path.unlink(missing_ok=True)
        log.info(f"Auto-deleted {path.name}")
    except Exception as e:
        log.warning(f"Failed to delete {path}: {e}")


async def download_via_ytdlp(url: str) -> Path | None:
    file_id = uuid.uuid4().hex
    out_template = str(AUDIO_DIR / f"{file_id}.%(ext)s")

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts(out_template)) as ydl:
            ydl.download([url])

    try:
        await asyncio.get_event_loop().run_in_executor(None, _download)
    except Exception as e:
        log.error(f"yt-dlp failed for {url}: {e}")
        return None

    matches = list(AUDIO_DIR.glob(f"{file_id}*.mp3"))
    if not matches:
        matches = list(AUDIO_DIR.glob(f"{file_id}*"))
    return matches[0] if matches else None


async def download_direct(url: str) -> Path | None:
    file_id = uuid.uuid4().hex
    suffix = Path(url.split("?")[0]).suffix or ".mp3"
    dest = AUDIO_DIR / f"{file_id}{suffix}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    return None
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(65536):
                        await f.write(chunk)
        return dest
    except Exception as e:
        log.error(f"Direct download failed: {e}")
        return None


def is_direct_audio(url: str) -> bool:
    return url.split("?")[0].lower().endswith((".mp3", ".ogg", ".flac", ".wav"))


@bot.event
async def on_ready():
    log.info(f"Leto Radio Bot ready as {bot.user} | Watching channel {CHANNEL_ID}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return

    urls = URL_RE.findall(message.content)
    if not urls:
        return

    for url in urls:
        await process_url(message, url)

    await bot.process_commands(message)


async def process_url(message: discord.Message, url: str):
    status = await message.reply(
        f"⏳ Downloading `{url[:70]}{'...' if len(url) > 70 else ''}`…",
        mention_author=False,
    )

    audio_file = await download_direct(url) if is_direct_audio(url) else await download_via_ytdlp(url)

    if not audio_file or not audio_file.exists():
        await status.edit(content="❌ Could not download audio. Make sure the link is public and supported.")
        return

    size_mb = audio_file.stat().st_size / 1_048_576
    radio_url = f"{PUBLIC_URL}/audio/{audio_file.name}"
    ttl_min = FILE_TTL // 60

    embed = discord.Embed(title="🎵 Leto Radio — Stream URL Ready", color=0x1db954)
    embed.add_field(
        name="📻 Paste into your Minecraft radio mod:",
        value=f"```\n{radio_url}\n```",
        inline=False,
    )
    embed.add_field(name="📦 Size", value=f"{size_mb:.1f} MB", inline=True)
    embed.add_field(name="⏱ Deletes in", value=f"{ttl_min} min", inline=True)
    embed.set_footer(text="Works with Simple Voice Chat Radio, Phonograph, IE Radio, and more")

    await status.edit(content=None, embed=embed)
    asyncio.create_task(schedule_deletion(audio_file, FILE_TTL))
    log.info(f"Served {audio_file.name} ({size_mb:.1f} MB) — deletes in {FILE_TTL}s")


bot.run(TOKEN)
