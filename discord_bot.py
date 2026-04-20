#!/usr/bin/env python3
"""
Leto Radio - Discord Bot
Watches the radio channel for song URLs and adds them to the queue.
"""

import os
import re
import asyncio
import json
import discord
from pathlib import Path
from dotenv import load_dotenv

import sys
sys.path.insert(0, str(Path(__file__).parent))
from queue_manager import QueueManager

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
RADIO_CHANNEL_NAME = os.getenv("RADIO_CHANNEL_NAME", "letoradio")
MUSIC_DIR = Path(os.getenv("MUSIC_DIR", "/data/music"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "20"))

MUSIC_DIR.mkdir(parents=True, exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
queue = QueueManager()

URL_REGEX = re.compile(r"https?://[^\s]+")


def is_supported_url(url: str) -> bool:
    supported = ["youtube.com", "youtu.be", "soundcloud.com", "bandcamp.com"]
    return any(domain in url for domain in supported)


async def download_song(url: str, requested_by: str, channel) -> dict | None:
    """Downloads a song using yt-dlp and returns song info."""
    safe_name = re.sub(r"[^a-zA-Z0-9]", "_", requested_by)[:20]
    output_template = str(MUSIC_DIR / f"{safe_name}_%(id)s.%(ext)s")

    # First get the title and id via --dump-json
    info_cmd = [
        "yt-dlp",
        "--dump-json",
        "--no-playlist",
        url,
    ]

    # Then download
    dl_cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "5",
        "--output", output_template,
        "--no-playlist",
        "--max-filesize", "50m",
        url,
    ]

    try:
        # Get metadata first
        info_proc = await asyncio.create_subprocess_exec(
            *info_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        info_stdout, _ = await asyncio.wait_for(info_proc.communicate(), timeout=30)
        
        title = "Unknown Title"
        video_id = None
        try:
            info = json.loads(info_stdout.decode())
            title = info.get("title", "Unknown Title")
            video_id = info.get("id")
        except Exception:
            pass

        # Download the audio
        dl_proc = await asyncio.create_subprocess_exec(
            *dl_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(dl_proc.communicate(), timeout=120)

        if dl_proc.returncode != 0:
            error = stderr.decode().strip().splitlines()[-1] if stderr else "Unknown error"
            await channel.send(f"❌ Couldn't download that. Error: `{error[:200]}`")
            return None

        # Find the downloaded mp3 — match by video id if we have it
        if video_id:
            matches = list(MUSIC_DIR.glob(f"{safe_name}_{video_id}.mp3"))
        else:
            matches = sorted(MUSIC_DIR.glob(f"{safe_name}_*.mp3"), key=lambda f: f.stat().st_mtime)

        if not matches:
            await channel.send("❌ Download seemed to work but I couldn't find the file.")
            return None

        filepath = str(matches[-1])

        return {
            "title": title,
            "requested_by": requested_by,
            "original_url": url,
            "filepath": filepath,
        }

    except asyncio.TimeoutError:
        await channel.send("❌ Download timed out (over 2 minutes). Try a shorter song!")
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
    if message.author.bot:
        return

    if message.channel.name != RADIO_CHANNEL_NAME:
        return

    content = message.content.strip()

    if content.lower() == "!queue":
        q = queue.get_all()
        if not q:
            await message.channel.send("📭 The queue is empty! Drop a link to add a song.")
            return
        lines = [f"**Queue ({len(q)} songs):**"]
        for i, song in enumerate(q):
            prefix = "▶️" if i == 0 else f"{i}."
            lines.append(f"{prefix} {song['title']} — requested by {song['requested_by']}")
        await message.channel.send("\n".join(lines[:15]))
        return

    if content.lower() in ("!nowplaying", "!np"):
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
            "Paste a YouTube, SoundCloud, or Bandcamp link to queue a song!\n"
            "`!queue` — See what's coming up\n"
            "`!np` — See what's playing now\n"
            "`!help` — This message"
        )
        return

    urls = URL_REGEX.findall(content)
    if not urls:
        return

    url = urls[0]

    current_queue = queue.get_all()
    if len(current_queue) >= MAX_QUEUE_SIZE:
        await message.channel.send(f"📋 Queue is full ({MAX_QUEUE_SIZE} songs)! Wait for some to play first.")
        return

    status_msg = await message.channel.send(f"⏳ Downloading your song, {message.author.display_name}...")

    song_info = await download_song(url, message.author.display_name, message.channel)

    if song_info:
        queue.add(song_info)
        position = len(queue.get_all())
        if position == 1:
            await status_msg.edit(content=f"✅ **{song_info['title']}** is up next (playing now)!")
        else:
            await status_msg.edit(content=f"✅ **{song_info['title']}** added to queue at position {position}.")
    else:
        await status_msg.edit(content="❌ Failed to add song.")


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        exit(1)
    client.run(DISCORD_TOKEN)
