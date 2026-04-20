#!/usr/bin/env python3
"""
Leto Radio - Discord Bot
Watches the #leto-radio channel for song URLs and adds them to the queue.
"""

import os
import re
import asyncio
import subprocess
import discord
from pathlib import Path
from dotenv import load_dotenv

# Local import — run from the leto-radio directory
import sys
sys.path.insert(0, str(Path(__file__).parent))
from queue_manager import QueueManager

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RADIO_CHANNEL_NAME = os.getenv("RADIO_CHANNEL_NAME", "leto-radio")
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/home/pi/leto-radio/music"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "20"))

MUSIC_DIR.mkdir(parents=True, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
queue = QueueManager()

# Regex to find URLs in messages
URL_REGEX = re.compile(r"https?://[^\s]+")


def is_supported_url(url: str) -> bool:
    """Basic check for supported platforms."""
    supported = [
        "youtube.com", "youtu.be",
        "soundcloud.com",
        "bandcamp.com",
        "spotify.com",  # yt-dlp can handle some spotify via youtube music
    ]
    return any(domain in url for domain in supported)


async def download_song(url: str, requested_by: str, channel) -> dict | None:
    """Downloads a song using yt-dlp and returns song info."""
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", requested_by)[:20]
    output_template = str(MUSIC_DIR / f"{safe_name}_%(id)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",      # ~128kbps, good for MC
        "--output", output_template,
        "--print", "%(title)s|||%(duration)s|||%(filepath)s",
        "--no-playlist",
        "--max-filesize", "50m",     # safety limit
        url,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            error = stderr.decode().strip().splitlines()[-1] if stderr else "Unknown error"
            await channel.send(f"❌ Couldn't download that song. Error: `{error[:200]}`")
            return None

        output = stdout.decode().strip().splitlines()[-1]  # last line has the info
        parts = output.split("|||")

        if len(parts) < 3:
            # Fallback: find the file manually
            files = list(MUSIC_DIR.glob(f"{safe_name}_*.mp3"))
            if not files:
                await channel.send("❌ Download seemed to work but I couldn't find the file.")
                return None
            filepath = str(sorted(files)[-1])
            title = "Unknown Title"
        else:
            title = parts[0].strip()
            filepath = parts[2].strip()

            # yt-dlp might print .webm path even when mp3 was requested
            # make sure we have the mp3
            filepath = filepath.replace(".webm", ".mp3").replace(".m4a", ".mp3")

        return {
            "title": title,
            "requested_by": requested_by,
            "original_url": url,
            "filepath": filepath,
        }

    except asyncio.TimeoutError:
        await channel.send("❌ Download timed out (took over 2 minutes). Try a shorter song!")
        return None
    except Exception as e:
        await channel.send(f"❌ Something went wrong: `{str(e)[:200]}`")
        return None


@client.event
async def on_ready():
    print(f"[bot] Logged in as {client.user}")
    print(f"[bot] Watching #{RADIO_CHANNEL_NAME} for song requests")


@client.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return

    # Only handle messages in the radio channel
    if message.channel.name != RADIO_CHANNEL_NAME:
        return

    content = message.content.strip()

    # --- Commands ---
    if content.lower() == "!queue":
        q = queue.get_all()
        if not q:
            await message.channel.send("📭 The queue is empty! Drop a link to add a song.")
            return
        lines = [f"**Queue ({len(q)} songs):**"]
        for i, song in enumerate(q):
            prefix = "▶️" if i == 0 else f"{i}."
            lines.append(f"{prefix} {song['title']} — requested by {song['requested_by']}")
        await message.channel.send("\n".join(lines[:15]))  # Discord limit safety
        return

    if content.lower() == "!nowplaying" or content.lower() == "!np":
        q = queue.get_all()
        if not q:
            await message.channel.send("🔇 Nothing is playing right now.")
        else:
            song = q[0]
            await message.channel.send(f"▶️ Now playing: **{song['title']}** (requested by {song['requested_by']})")
        return

    if content.lower() == "!help":
        await message.channel.send(
            "🎵 **Leto Radio Commands**\n"
            "Just paste a YouTube, SoundCloud, or Bandcamp link to queue a song!\n"
            "`!queue` — See what's coming up\n"
            "`!np` — See what's playing now\n"
            "`!help` — This message"
        )
        return

    # --- URL detection ---
    urls = URL_REGEX.findall(content)
    if not urls:
        return  # Not a command, not a URL — ignore

    url = urls[0]  # Take the first URL found

    if not is_supported_url(url):
        await message.channel.send(
            f"⚠️ I'm not sure I can play that. Supported: YouTube, SoundCloud, Bandcamp.\n"
            f"Try anyway? (Attempting download...)"
        )

    # Check queue size
    current_queue = queue.get_all()
    if len(current_queue) >= MAX_QUEUE_SIZE:
        await message.channel.send(f"📋 The queue is full ({MAX_QUEUE_SIZE} songs)! Wait for some to play first.")
        return

    # Download and queue
    status_msg = await message.channel.send(f"⏳ Downloading your song, {message.author.display_name}...")

    song_info = await download_song(url, message.author.display_name, message.channel)

    if song_info:
        queue.add(song_info)
        position = len(queue.get_all())
        if position == 1:
            await status_msg.edit(content=f"✅ **{song_info['title']}** is up next (playing now)!")
        else:
            await status_msg.edit(content=f"✅ **{song_info['title']}** added to queue at position {position}.")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set in .env file!")
        exit(1)
    client.run(DISCORD_TOKEN)
