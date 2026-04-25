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
TOKEN          = os.environ["DISCORD_TOKEN"]
CHANNEL_ID     = int(os.environ["DISCORD_CHANNEL_ID"])
PUBLIC_URL     = os.environ["PUBLIC_URL"].rstrip("/")   # e.g. https://radio.example.com
FILE_TTL       = int(os.environ.get("FILE_TTL_SECONDS", 3600))  # default 1 hour
AUDIO_DIR      = Path(os.environ.get("AUDIO_DIR", "/audio"))
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# ── URL patterns we care about ─────────────────────────────────────────────────
URL_RE = re.compile(
    r"https?://"
    r"(?:www\.)?"
    r"(?:"
    r"youtube\.com/watch\?[^\s]*v=[\w-]+"
    r"|youtu\.be/[\w-]+"
    r"|soundcloud\.com/[\w/-]+"
    r"|[\w.-]+\.mp3(?:\?[^\s]*)?"       # direct .mp3 links
    r"|[\w.-]+\.ogg(?:\?[^\s]*)?"
    r"|[\w.-]+\.flac(?:\?[^\s]*)?"
    r"|[\w.-]+\.wav(?:\?[^\s]*)?"
    r"|open\.spotify\.com/track/[\w]+"  # spotify (yt-dlp handles some)
    r"|bandcamp\.com/[\w/-]+"
    r"|[\w.-]+/[\w/.-]+\.(?:mp3|ogg|flac|wav)(?:\?[^\s]*)?"  # generic audio
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

# ── Bot setup ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def schedule_deletion(path: Path, delay: int):
    """Delete a file after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        path.unlink(missing_ok=True)
        log.info(f"Auto-deleted {path.name}")
    except Exception as e:
        log.warning(f"Failed to delete {path}: {e}")


async def download_audio(url: str) -> Path | None:
    """Download audio from any yt-dlp-supported URL. Returns the .mp3 path."""
    file_id = uuid.uuid4().hex
    out_template = str(AUDIO_DIR / f"{file_id}.%(ext)s")

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(ydl_opts(out_template)) as ydl:
            ydl.download([url])

    try:
        await loop.run_in_executor(None, _download)
    except Exception as e:
        log.error(f"yt-dlp failed for {url}: {e}")
        return None

    # yt-dlp may rename the file; find it
    matches = list(AUDIO_DIR.glob(f"{file_id}*.mp3"))
    if not matches:
        matches = list(AUDIO_DIR.glob(f"{file_id}*"))
    return matches[0] if matches else None


async def download_direct_mp3(url: str) -> Path | None:
    """Download a raw .mp3/audio file directly."""
    file_id = uuid.uuid4().hex
    suffix = Path(url.split("?")[0]).suffix or ".mp3"
    dest = AUDIO_DIR / f"{file_id}{suffix}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    return None
                async with aiofiles.open(dest, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 64):
                        await f.write(chunk)
        return dest
    except Exception as e:
        log.error(f"Direct download failed for {url}: {e}")
        return None


def is_direct_audio(url: str) -> bool:
    clean = url.split("?")[0].lower()
    return clean.endswith((".mp3", ".ogg", ".flac", ".wav"))


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user} | Watching channel {CHANNEL_ID}")


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
    status_msg = await message.reply(
        f"⏳ Downloading `{url[:60]}{'...' if len(url)>60 else ''}`…",
        mention_author=False,
    )

    # Try direct download first for raw audio links (faster)
    if is_direct_audio(url):
        audio_file = await download_direct_mp3(url)
    else:
        audio_file = await download_audio(url)

    if not audio_file or not audio_file.exists():
        await status_msg.edit(content="❌ Failed to download audio. Make sure the link is public and supported.")
        return

    size_mb = audio_file.stat().st_size / 1_048_576
    radio_url = f"{PUBLIC_URL}/audio/{audio_file.name}"
    ttl_min = FILE_TTL // 60

    embed = discord.Embed(
        title="🎵 Minecraft Radio Link Ready",
        color=0x2ecc71,
    )
    embed.add_field(
        name="📻 Paste this URL into your Minecraft radio mod:",
        value=f"```\n{radio_url}\n```",
        inline=False,
    )
    embed.add_field(name="📦 File size", value=f"{size_mb:.1f} MB", inline=True)
    embed.add_field(name="⏱ Auto-deletes in", value=f"{ttl_min} minutes", inline=True)
    embed.set_footer(text="Works with: Simple Voice Chat Radio, Phonograph, IE Speakers, and most radio mods")

    await status_msg.edit(content=None, embed=embed)

    # Schedule deletion
    asyncio.create_task(schedule_deletion(audio_file, FILE_TTL))
    log.info(f"Served {audio_file.name} ({size_mb:.1f} MB) → scheduled deletion in {FILE_TTL}s")


bot.run(TOKEN)
