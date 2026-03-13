"""Video processor — extract frames + audio from video via ffmpeg."""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from dataclasses import dataclass, field

import structlog

from src.engine.supabase_client import get_client

logger = structlog.get_logger(__name__)


@dataclass
class VideoResult:
    """Result of video processing."""
    frames: list[bytes] = field(default_factory=list)
    audio_bytes: bytes | None = None
    audio_filename: str = "extracted_audio.ogg"
    frame_count: int = 0
    duration_seconds: float = 0.0


async def process_video(storage_path: str) -> VideoResult:
    """Download video from Supabase Storage and extract frames + audio.

    Extracts 1 frame every 5 seconds and the full audio track.
    """
    start = time.time()
    logger.info("video_process_start", storage_path=storage_path)

    result = VideoResult()
    tmpdir = tempfile.mkdtemp(prefix="fge_video_")

    try:
        # Download video from Storage
        sb = get_client()
        video_bytes = sb.storage.from_("media").download(storage_path)

        video_path = os.path.join(tmpdir, "input_video.mp4")
        with open(video_path, "wb") as f:
            f.write(video_bytes)

        # Extract frames: 1 every 10 seconds
        frames_pattern = os.path.join(tmpdir, "frame_%04d.jpg")
        frame_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", video_path,
            "-vf", "fps=1/5",
            "-q:v", "2",
            frames_pattern,
            "-y", "-loglevel", "error",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await frame_proc.communicate()
        if frame_proc.returncode != 0:
            logger.error("ffmpeg_frames_failed", error=stderr.decode())

        # Read extracted frames
        frame_files = sorted(
            f for f in os.listdir(tmpdir) if f.startswith("frame_") and f.endswith(".jpg")
        )
        for frame_file in frame_files:
            frame_path = os.path.join(tmpdir, frame_file)
            with open(frame_path, "rb") as f:
                result.frames.append(f.read())

        result.frame_count = len(result.frames)

        # Extract audio
        audio_path = os.path.join(tmpdir, "extracted_audio.ogg")
        audio_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", video_path,
            "-vn", "-acodec", "libopus",
            audio_path,
            "-y", "-loglevel", "error",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await audio_proc.communicate()
        if audio_proc.returncode == 0 and os.path.exists(audio_path):
            with open(audio_path, "rb") as f:
                result.audio_bytes = f.read()

        # Get duration
        probe_proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-i", video_path,
            "-f", "null", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, probe_stderr = await probe_proc.communicate()
        duration_line = [
            l for l in probe_stderr.decode().split("\n") if "Duration" in l
        ]
        if duration_line:
            try:
                time_str = duration_line[0].split("Duration:")[1].split(",")[0].strip()
                parts = time_str.split(":")
                result.duration_seconds = (
                    float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                )
            except (IndexError, ValueError):
                pass

        elapsed_ms = int((time.time() - start) * 1000)
        logger.info(
            "video_process_complete",
            frames=result.frame_count,
            has_audio=result.audio_bytes is not None,
            duration_s=result.duration_seconds,
            elapsed_ms=elapsed_ms,
        )
        return result

    except Exception as e:
        logger.error("video_process_failed", storage_path=storage_path, error=str(e))
        return result

    finally:
        # Cleanup temp files
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)
