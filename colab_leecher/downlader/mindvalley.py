# copyright 2025 © theSadeQ | https://github.com/theSadeQ/Telegram-Leecher

"""
Mindvalley Course Downloader
Downloads video, audio, and subtitle streams from Mindvalley M3U8 playlists
Integrated with Telegram-Leecher bot
"""

import asyncio
import os
import re
import logging
import shutil
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urljoin

import aiohttp
from pyrogram.types import Message

from colab_leecher.utility.variables import Paths, MSG, BotTimes, Messages
from colab_leecher.utility.helper import sizeUnit, speedETA, status_bar, getTime
from colab_leecher.utility.task_context import TaskContext

log = logging.getLogger(__name__)


class MindvalleyDownloader:
    """Handles Mindvalley M3U8 stream downloads"""

    def __init__(self, client, message: Message, task_ctx: TaskContext = None):
        self.client = client
        self.message = message
        self.task_ctx = task_ctx  # NEW: Per-task context for parallel downloads

        # Use task-specific download directory if task_ctx provided, otherwise global
        if task_ctx:
            self.download_dir = task_ctx.down_path
        else:
            self.download_dir = Paths.down_path  # Fallback to global for backward compat

        # Progress tracking
        self.download_start_time = 0
        self.total_downloaded = 0
        self.total_size = 0
        self.current_stream_type = ""

        # Auto-detect available downloader
        self.downloader = self._detect_downloader()
        log.info(f"Mindvalley downloader initialized with: {self.downloader} (task: {task_ctx.get_short_id() if task_ctx else 'legacy'})")

    def _detect_downloader(self) -> str:
        """Detect which M3U8 downloader is available"""
        # Check for N_m3u8DL-RE (preferred for Colab)
        if shutil.which("N_m3u8DL-RE"):
            log.info("Found N_m3u8DL-RE")
            return "n_m3u8dl"

        # Check for yt-dlp (fallback, works on Windows and Linux)
        if shutil.which("yt-dlp"):
            log.info("Found yt-dlp (fallback)")
            return "ytdlp"

        # Check for ffmpeg (last resort)
        if shutil.which("ffmpeg"):
            log.info("Found ffmpeg (basic fallback)")
            return "ffmpeg"

        log.error("No M3U8 downloader found! Install N_m3u8DL-RE, yt-dlp, or ffmpeg")
        return "none"

    def _parse_vtt_duration(self, vtt_path: str) -> Optional[float]:
        """
        Parse VTT subtitle file and extract the duration (last timestamp)

        Args:
            vtt_path: Path to VTT file

        Returns:
            Duration in seconds, or None if parsing fails
        """
        try:
            with open(vtt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all timestamps in format: HH:MM:SS.mmm --> HH:MM:SS.mmm
            timestamp_pattern = r'(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})'
            matches = re.findall(timestamp_pattern, content)

            if not matches:
                log.warning(f"No timestamps found in VTT file: {vtt_path}")
                return None

            # Get the last end timestamp (second timestamp in the match)
            last_match = matches[-1]
            hours = int(last_match[4])
            minutes = int(last_match[5])
            seconds = int(last_match[6])
            milliseconds = int(last_match[7])

            # Convert to seconds
            total_seconds = hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0
            log.info(f"VTT duration: {total_seconds:.2f}s ({hours:02d}:{minutes:02d}:{seconds:02d})")
            return total_seconds

        except Exception as e:
            log.error(f"Failed to parse VTT duration: {e}")
            return None

    async def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get video duration using ffprobe

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds, or None if detection fails
        """
        try:
            # Check if ffprobe is available
            if not shutil.which("ffprobe"):
                log.warning("ffprobe not found, cannot validate video duration")
                return None

            cmd = [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                duration_str = stdout.decode('utf-8').strip()
                duration = float(duration_str)
                log.info(f"Video duration: {duration:.2f}s")
                return duration
            else:
                log.error(f"ffprobe failed: {stderr.decode('utf-8')}")
                return None

        except Exception as e:
            log.error(f"Failed to get video duration: {e}")
            return None

    async def download_stream(
        self,
        m3u8_url: str,
        filename: str,
        stream_type: str = "video"
    ) -> Tuple[bool, Optional[str]]:
        """
        Download M3U8 stream using available downloader

        Args:
            m3u8_url: M3U8 playlist URL
            filename: Output filename (without extension)
            stream_type: Type of stream (video/audio/subtitle) for logging

        Returns:
            Tuple of (success: bool, output_path: Optional[str])
        """
        # Check if any downloader is available
        if self.downloader == "none":
            error_msg = "❌ No M3U8 downloader installed! Install N_m3u8DL-RE, yt-dlp, or ffmpeg"
            log.error(error_msg)
            # Show error in progress bar format
            status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg
            if status_msg:
                await self.update_progress_bar(0.0, error_msg)
            return False, None

        # Route to appropriate downloader
        if self.downloader == "n_m3u8dl":
            return await self._download_with_n_m3u8dl(m3u8_url, filename, stream_type)
        elif self.downloader == "ytdlp":
            return await self._download_with_ytdlp(m3u8_url, filename, stream_type)
        elif self.downloader == "ffmpeg":
            return await self._download_with_ffmpeg(m3u8_url, filename, stream_type)

    async def _download_with_n_m3u8dl(
        self,
        m3u8_url: str,
        filename: str,
        stream_type: str = "video"
    ) -> Tuple[bool, Optional[str]]:
        """Download using N_m3u8DL-RE"""
        try:
            # Ensure download directory exists
            os.makedirs(self.download_dir, exist_ok=True)

            # Initialize progress tracking
            self.download_start_time = time.time()
            self.current_stream_type = stream_type
            self.current_percentage = 0.0

            # Build command
            cmd = [
                "N_m3u8DL-RE",
                m3u8_url,
                "--save-name", filename,
                "--save-dir", str(self.download_dir),
                "--log-level", "INFO",
                "--binary-merge"  # Faster merging
            ]

            log.info(f"Starting {stream_type} download with N_m3u8DL-RE: {filename}")

            # Show initial progress bar at 0%
            await self.update_progress_bar(0.0)

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024*1024  # Increase buffer limit to 1MB
            )

            # Monitor progress
            last_update = 0
            while True:
                try:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    output = line.decode('utf-8', errors='ignore').strip()
                    log.debug(f"N_m3u8DL-RE: {output[:200]}...")

                    # Parse progress (N_m3u8DL-RE shows percentage)
                    if '%' in output and time.time() - last_update > 2.5:
                        # Extract percentage
                        percentage_match = re.search(r'(\d+\.?\d*)%', output)
                        if percentage_match:
                            percentage_float = float(percentage_match.group(1))
                            self.current_percentage = percentage_float

                            # NEW: Try to extract download speed (N_m3u8DL-RE format may vary)
                            speed_str = None
                            # Pattern: "5.2 MB/s" or "5.2MB/s" or "5.2 MiB/s"
                            speed_match = re.search(r'(\d+\.?\d+)\s*(KB|MB|GB|KiB|MiB|GiB)/s', output, re.IGNORECASE)
                            if speed_match:
                                speed_value = speed_match.group(1)
                                speed_unit = speed_match.group(2).upper()
                                # Normalize to MB/s
                                if "GIB" in speed_unit or "GB" in speed_unit:
                                    speed_str = f"{float(speed_value) * 1024:.1f} MB/s"
                                elif "MIB" in speed_unit or "MB" in speed_unit:
                                    speed_str = f"{speed_value} MB/s"
                                elif "KIB" in speed_unit or "KB" in speed_unit:
                                    speed_str = f"{float(speed_value) / 1024:.2f} MB/s"

                            # NEW: Try to extract segment info (e.g., "150/300" or "Seg 150/300")
                            segments_done = None
                            segments_total = None
                            # Pattern: number/number (e.g., "150/300")
                            seg_match = re.search(r'(\d+)/(\d+)', output)
                            if seg_match:
                                # Make sure this isn't a time (like 01:25)
                                if int(seg_match.group(2)) > 59:  # Likely segments, not time
                                    segments_done = int(seg_match.group(1))
                                    segments_total = int(seg_match.group(2))

                            # Update progress bar with all available info
                            await self.update_progress_bar(
                                percentage_float,
                                speed=speed_str,
                                segments_done=segments_done,
                                segments_total=segments_total
                            )
                            last_update = time.time()
                except asyncio.LimitOverrunError:
                    log.warning("Skipped extremely long output line from N_m3u8DL-RE")
                    continue

            # Wait for process to complete
            await process.wait()

            if process.returncode == 0:
                # Find output file (N_m3u8DL-RE adds extension automatically)
                possible_extensions = ['.mp4', '.m4a', '.ts']
                output_path = None

                for ext in possible_extensions:
                    potential_path = Path(self.download_dir) / f"{filename}{ext}"
                    if potential_path.exists():
                        output_path = str(potential_path)
                        break

                if output_path:
                    file_size = os.path.getsize(output_path)
                    log.info(f"{stream_type.capitalize()} downloaded: {output_path} ({sizeUnit(file_size)})")
                    # Show 100% completion with file size
                    await self.update_progress_bar(100.0, f"Complete ✅ {sizeUnit(file_size)}")
                    return True, output_path
                else:
                    log.error(f"Download completed but output file not found: {filename}")
                    await self.update_progress_bar(self.current_percentage, "❌ File not found")
                    return False, None
            else:
                log.error(f"{stream_type.capitalize()} download failed with code {process.returncode}")
                await self.update_progress_bar(self.current_percentage, f"❌ Download failed")
                return False, None

        except Exception as e:
            log.exception(f"Error downloading {stream_type} with N_m3u8DL-RE")
            await self.update_progress_bar(self.current_percentage, f"❌ Error occurred")
            return False, None

    async def _download_with_ytdlp(
        self,
        m3u8_url: str,
        filename: str,
        stream_type: str = "video"
    ) -> Tuple[bool, Optional[str]]:
        """Download using yt-dlp (fallback, works on Windows and Linux)"""
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            output_template = str(Path(self.download_dir) / f"{filename}.%(ext)s")

            # Initialize progress tracking
            self.download_start_time = time.time()
            self.current_stream_type = stream_type
            self.current_percentage = 0.0

            cmd = [
                "yt-dlp",
                "-o", output_template,
                "--no-warnings",
                "--no-check-certificate",
                m3u8_url
            ]

            log.info(f"Starting {stream_type} download with yt-dlp: {filename}")

            # Show initial progress bar at 0%
            await self.update_progress_bar(0.0)

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024*1024  # Increase buffer limit to 1MB for long lines
            )

            # Monitor progress
            last_update = 0
            while True:
                try:
                    line = await process.stdout.readline()
                    if not line:
                        break

                    output = line.decode('utf-8', errors='ignore').strip()
                    log.debug(f"yt-dlp: {output[:200]}...")

                    # Parse yt-dlp progress
                    if '%' in output and time.time() - last_update > 2.5:
                        # Extract percentage
                        percentage_match = re.search(r'(\d+\.?\d*)%', output)
                        if percentage_match:
                            percentage_float = float(percentage_match.group(1))
                            self.current_percentage = percentage_float

                            # NEW: Try to extract download speed (e.g., "5.20MiB/s")
                            speed_str = None
                            speed_match = re.search(r'at\s+(\d+\.?\d+)\s*(B|KiB|MiB|GiB)/s', output)
                            if speed_match:
                                speed_value = speed_match.group(1)
                                speed_unit = speed_match.group(2)
                                # Convert to MB/s for consistency
                                if speed_unit == "GiB":
                                    speed_str = f"{float(speed_value) * 1024:.1f} MB/s"
                                elif speed_unit == "MiB":
                                    speed_str = f"{speed_value} MB/s"
                                elif speed_unit == "KiB":
                                    speed_str = f"{float(speed_value) / 1024:.2f} MB/s"
                                else:  # B
                                    speed_str = f"{float(speed_value) / (1024*1024):.2f} MB/s"

                            # NEW: Try to extract fragment/segment info (e.g., "frag 45/120")
                            segments_done = None
                            segments_total = None
                            frag_match = re.search(r'frag[ment]*\s+(\d+)/(\d+)', output)
                            if frag_match:
                                segments_done = int(frag_match.group(1))
                                segments_total = int(frag_match.group(2))

                            # Update progress bar with all available info
                            await self.update_progress_bar(
                                percentage_float,
                                speed=speed_str,
                                segments_done=segments_done,
                                segments_total=segments_total
                            )
                            last_update = time.time()
                except asyncio.LimitOverrunError:
                    log.warning("Skipped extremely long output line from yt-dlp")
                    continue

            await process.wait()

            if process.returncode == 0:
                # Find the downloaded file
                possible_extensions = ['.mp4', '.mkv', '.webm', '.m4a', '.ts']
                output_path = None

                for ext in possible_extensions:
                    potential_path = Path(self.download_dir) / f"{filename}{ext}"
                    if potential_path.exists():
                        output_path = str(potential_path)
                        break

                if output_path:
                    file_size = os.path.getsize(output_path)
                    log.info(f"{stream_type.capitalize()} downloaded: {output_path} ({sizeUnit(file_size)})")
                    # Show 100% completion with file size
                    await self.update_progress_bar(100.0, f"Complete ✅ {sizeUnit(file_size)}")
                    return True, output_path
                else:
                    log.error(f"yt-dlp download completed but output file not found: {filename}")
                    await self.update_progress_bar(self.current_percentage, "❌ File not found")
                    return False, None
            else:
                log.error(f"yt-dlp download failed with code {process.returncode}")
                await self.update_progress_bar(self.current_percentage, "❌ Download failed")
                return False, None

        except Exception as e:
            log.exception(f"Error downloading {stream_type} with yt-dlp")
            await self.update_progress_bar(self.current_percentage, "❌ Error occurred")
            return False, None

    async def _download_with_ffmpeg(
        self,
        m3u8_url: str,
        filename: str,
        stream_type: str = "video"
    ) -> Tuple[bool, Optional[str]]:
        """Download using ffmpeg directly (basic fallback)"""
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            output_path = Path(self.download_dir) / f"{filename}.mp4"

            # Initialize progress tracking
            self.download_start_time = time.time()
            self.current_stream_type = stream_type
            self.current_percentage = 0.0

            cmd = [
                "ffmpeg",
                "-y",  # Overwrite
                "-i", m3u8_url,
                "-c", "copy",  # Copy streams without re-encoding
                "-bsf:a", "aac_adtstoasc",  # Fix AAC bitstream
                str(output_path)
            ]

            log.info(f"Starting {stream_type} download with ffmpeg: {filename}")

            # Show initial progress bar
            await self.update_progress_bar(0.0, "Processing...")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024*1024  # Increase buffer limit to 1MB
            )

            # Monitor output (ffmpeg outputs to stderr)
            while True:
                try:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    output = line.decode('utf-8', errors='ignore').strip()
                    log.debug(f"ffmpeg: {output[:200]}...")
                except asyncio.LimitOverrunError:
                    log.warning("Skipped extremely long output line from ffmpeg")
                    continue

            await process.wait()

            if process.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                log.info(f"{stream_type.capitalize()} downloaded: {output_path} ({sizeUnit(file_size)})")
                await self.update_progress_bar(100.0, f"Complete ✅ {sizeUnit(file_size)}")
                return True, str(output_path)
            else:
                log.error(f"ffmpeg download failed with code {process.returncode}")
                await self.update_progress_bar(0.0, "❌ Download failed")
                return False, None

        except Exception as e:
            log.exception(f"Error downloading {stream_type} with ffmpeg")
            await self.update_progress_bar(0.0, "❌ Error occurred")
            return False, None

    async def download_subtitle(
        self,
        m3u8_url: str,
        filename: str = "subtitle.vtt"
    ) -> Tuple[bool, Optional[str]]:
        """
        Download and merge VTT subtitle segments from M3U8 playlist

        Args:
            m3u8_url: Subtitle M3U8 playlist URL
            filename: Output filename

        Returns:
            Tuple of (success: bool, output_path: Optional[str])
        """
        try:
            os.makedirs(self.download_dir, exist_ok=True)
            output_path = Path(self.download_dir) / filename

            # Initialize progress tracking for subtitles
            self.download_start_time = time.time()
            self.current_stream_type = "subtitle"
            self.current_percentage = 0.0

            log.info(f"Downloading subtitle playlist: {m3u8_url}")
            await self.update_progress_bar(0.0, "Fetching playlist...")

            # Download playlist
            async with aiohttp.ClientSession() as session:
                async with session.get(m3u8_url) as response:
                    if response.status != 200:
                        log.error(f"Failed to fetch subtitle playlist: HTTP {response.status}")
                        await self.update_progress_bar(0.0, "❌ Playlist not found")
                        return False, None

                    playlist_content = await response.text()

            # Parse segment URLs
            segments = []
            base_url = m3u8_url.rsplit('/', 1)[0] + '/'

            for line in playlist_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    if line.startswith('http'):
                        segments.append(line)
                    else:
                        segments.append(urljoin(base_url, line))

            if not segments:
                log.error("No subtitle segments found in playlist")
                await self.update_progress_bar(0.0, "❌ No segments found")
                return False, None

            log.info(f"Found {len(segments)} subtitle segments")
            total_segments = len(segments)
            await self.update_progress_bar(5.0, f"Downloading segments (0/{total_segments})")

            # Download and merge segments with retry logic
            merged_content = []
            first_segment = True
            failed_segments = []
            MAX_RETRIES = 2  # Retry failed segments once

            async with aiohttp.ClientSession() as session:
                for i, segment_url in enumerate(segments, 1):
                    success = False
                    for attempt in range(MAX_RETRIES):
                        try:
                            async with session.get(segment_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                                if response.status != 200:
                                    log.warning(f"Failed to download segment {i}/{total_segments} (HTTP {response.status}), attempt {attempt + 1}/{MAX_RETRIES}")
                                    if attempt < MAX_RETRIES - 1:
                                        await asyncio.sleep(1)  # Wait before retry
                                        continue
                                    else:
                                        failed_segments.append(i)
                                        break

                                content = await response.text()

                                # Skip WEBVTT header for non-first segments
                                if not first_segment:
                                    lines = content.split('\n')
                                    if lines and lines[0].startswith('WEBVTT'):
                                        content = '\n'.join(lines[1:])

                                merged_content.append(content)
                                first_segment = False
                                success = True
                                break  # Success, no need to retry

                        except Exception as e:
                            log.warning(f"Error downloading segment {i}: {e}, attempt {attempt + 1}/{MAX_RETRIES}")
                            if attempt < MAX_RETRIES - 1:
                                await asyncio.sleep(1)  # Wait before retry
                            else:
                                failed_segments.append(i)

                    # Update progress based on segment count
                    percentage = (i / total_segments) * 95  # Reserve 5% for writing
                    if i % 5 == 0 or i == total_segments:
                        status_text = f"Segments {i}/{total_segments}"
                        if failed_segments:
                            status_text += f" ({len(failed_segments)} failed)"
                        await self.update_progress_bar(percentage, status_text)

            # Check if too many segments failed (more than 10% = failure)
            failure_threshold = max(1, int(total_segments * 0.1))  # At least 1 segment, or 10% of total
            if len(failed_segments) > failure_threshold:
                error_msg = f"❌ Too many failed segments: {len(failed_segments)}/{total_segments} failed"
                log.error(f"Subtitle download failed: {error_msg}")
                await self.update_progress_bar(95.0, error_msg)
                return False, None

            # Write merged subtitle file
            final_content = '\n'.join(merged_content)
            output_path.write_text(final_content, encoding='utf-8')

            file_size = output_path.stat().st_size
            success_msg = f"Complete ✅ {sizeUnit(file_size)}"
            if failed_segments:
                success_msg += f" ({len(failed_segments)} segments skipped)"
                log.warning(f"Subtitle saved with {len(failed_segments)} failed segments: {output_path}")
            else:
                log.info(f"Subtitle saved: {output_path} ({sizeUnit(file_size)})")

            await self.update_progress_bar(100.0, success_msg)

            return True, str(output_path)

        except Exception as e:
            log.exception("Error downloading subtitle")
            await self.update_progress_bar(self.current_percentage, "❌ Subtitle error")
            return False, None

    async def merge_streams(
        self,
        video_path: str,
        audio_path: Optional[str] = None,
        subtitle_path: Optional[str] = None,
        output_filename: str = "final_output.mp4"
    ) -> Tuple[bool, Optional[str]]:
        """
        Merge video, audio, and subtitle streams using FFmpeg

        Args:
            video_path: Path to video file
            audio_path: Path to audio file (optional)
            subtitle_path: Path to subtitle file (optional)
            output_filename: Output filename

        Returns:
            Tuple of (success: bool, output_path: Optional[str])
        """
        try:
            output_path = Path(self.download_dir) / output_filename

            # Initialize progress for merging
            self.download_start_time = time.time()
            self.current_stream_type = "video"  # Keep as video for display
            self.current_percentage = 0.0

            # Build FFmpeg command
            cmd = ["ffmpeg", "-y"]  # -y to overwrite

            # Add inputs
            cmd.extend(["-i", video_path])
            if audio_path:
                cmd.extend(["-i", audio_path])
            if subtitle_path:
                cmd.extend(["-i", subtitle_path])

            # Map streams and set codecs
            map_idx = 0
            cmd.extend(["-map", f"{map_idx}:v"])  # Map video
            map_idx += 1

            if audio_path:
                cmd.extend(["-map", f"{map_idx}:a"])  # Map audio
                map_idx += 1

            if subtitle_path:
                cmd.extend(["-map", f"{map_idx}:s"])  # Map subtitle
                cmd.extend(["-c:s", "mov_text"])  # Subtitle codec for MP4

            # Copy video and audio (no re-encoding for speed)
            cmd.extend(["-c:v", "copy", "-c:a", "copy"])

            # Output file
            cmd.append(str(output_path))

            log.info(f"Merging streams: {' '.join(cmd)}")
            await self.update_progress_bar(0.0, "Merging streams...")

            # Run FFmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                limit=1024*1024  # Increase buffer limit to 1MB
            )

            # Monitor output
            while True:
                try:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    output = line.decode('utf-8', errors='ignore').strip()
                    log.debug(f"FFmpeg merge: {output[:200]}...")
                except asyncio.LimitOverrunError:
                    log.warning("Skipped extremely long output line from FFmpeg merge")
                    continue

            await process.wait()

            if process.returncode == 0 and output_path.exists():
                file_size = output_path.stat().st_size
                log.info(f"Merge successful: {output_path} ({sizeUnit(file_size)})")
                await self.update_progress_bar(100.0, f"Merged ✅ {sizeUnit(file_size)}")
                return True, str(output_path)
            else:
                log.error(f"Merge failed with code {process.returncode}")
                await self.update_progress_bar(0.0, "❌ Merge failed")
                return False, None

        except Exception as e:
            log.exception("Error merging streams")
            await self.update_progress_bar(0.0, "❌ Merge error")
            return False, None

    async def download_subtitle_only(
        self,
        subtitle_url: str,
        output_filename: str = "subtitle.vtt"
    ) -> Tuple[bool, Optional[str]]:
        """
        Download only subtitle without video/audio

        Args:
            subtitle_url: M3U8 subtitle URL
            output_filename: Output filename for subtitle

        Returns:
            Tuple of (success: bool, output_path: Optional[str])
        """
        log.info(f"Starting subtitle-only download: {subtitle_url}")

        # Download subtitle
        success, subtitle_path = await self.download_subtitle(subtitle_url, output_filename)

        if not success:
            log.error("Subtitle-only download failed")
            return False, None

        log.info(f"Subtitle-only download successful: {subtitle_path}")
        return True, subtitle_path

    async def download_and_merge(
        self,
        video_url: str,
        audio_url: Optional[str] = None,
        subtitle_url: Optional[str] = None,
        output_filename: str = "mindvalley_course.mp4"
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Complete download and merge workflow

        Args:
            video_url: M3U8 video URL
            audio_url: M3U8 audio URL (optional, for separate audio streams)
            subtitle_url: M3U8 subtitle URL (optional)
            output_filename: Final output filename

        Returns:
            Tuple of (success: bool, mp4_path: Optional[str], vtt_path: Optional[str])
        """
        # Download video (progress bar will be shown automatically)
        video_success, video_path = await self.download_stream(video_url, "video", "video")
        if not video_success:
            return False, None, None

        # Download audio (if separate)
        audio_path = None
        if audio_url:
            audio_success, audio_path = await self.download_stream(audio_url, "audio", "audio")
            if not audio_success:
                log.warning("Audio download failed, continuing with video only")

        # Download subtitles (if provided)
        subtitle_path = None
        vtt_path_for_upload = None
        if subtitle_url:
            subtitle_success, subtitle_path = await self.download_subtitle(subtitle_url)
            if subtitle_success and subtitle_path:
                # Validate subtitle duration against video duration
                subtitle_duration = self._parse_vtt_duration(subtitle_path)
                video_duration = await self._get_video_duration(video_path)

                if subtitle_duration and video_duration:
                    duration_ratio = subtitle_duration / video_duration
                    log.info(f"Subtitle/Video duration ratio: {duration_ratio:.2%} ({subtitle_duration:.1f}s / {video_duration:.1f}s)")

                    # Warn if subtitle is significantly shorter (less than 80% of video)
                    if duration_ratio < 0.80:
                        log.warning(f"⚠️ Subtitle duration ({subtitle_duration:.1f}s) is only {duration_ratio:.1%} of video duration ({video_duration:.1f}s)")
                        log.warning("This may indicate incomplete subtitle download!")
                    elif duration_ratio > 1.05:
                        log.warning(f"⚠️ Subtitle duration ({subtitle_duration:.1f}s) is longer than video duration ({video_duration:.1f}s)")
                    else:
                        log.info(f"✅ Subtitle duration matches video duration (ratio: {duration_ratio:.1%})")

                # Keep the VTT file for separate upload
                vtt_filename = output_filename.replace('.mp4', '.vtt')
                vtt_path_for_upload = str(Path(self.download_dir) / vtt_filename)

                # Copy the subtitle to final VTT path (don't rename, we still need original for merge)
                shutil.copy2(subtitle_path, vtt_path_for_upload)
                log.info(f"VTT file prepared for upload: {vtt_path_for_upload}")
            else:
                log.warning("Subtitle download failed, continuing without subtitles")

        # Merge if we have multiple streams
        if audio_path or subtitle_path:
            final_success, final_path = await self.merge_streams(
                video_path, audio_path, subtitle_path, output_filename
            )

            # Clean up individual files after successful merge
            if final_success:
                try:
                    if video_path and Path(video_path).exists():
                        Path(video_path).unlink()
                    if audio_path and Path(audio_path).exists():
                        Path(audio_path).unlink()
                    if subtitle_path and Path(subtitle_path).exists():
                        Path(subtitle_path).unlink()
                    log.info("Cleaned up temporary files (kept VTT for upload)")
                except Exception as e:
                    log.warning(f"Failed to clean up temp files: {e}")

            return final_success, final_path, vtt_path_for_upload
        else:
            # No merge needed, just rename video file
            final_path = Path(self.download_dir) / output_filename
            Path(video_path).rename(final_path)
            # Progress bar already shows completion from download_stream
            return True, str(final_path), vtt_path_for_upload

    async def update_progress_bar(
        self,
        percentage: float,
        status_text: str = "Downloading...",
        speed: str = None,  # NEW: Download speed (e.g., "5.2 MB/s")
        segments_done: int = None,  # NEW: Segments downloaded
        segments_total: int = None  # NEW: Total segments
    ):
        """Update progress bar using the bot's status_bar system"""
        try:
            # Use task_ctx.status_msg if available, otherwise fall back to global MSG
            status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg
            if not status_msg:
                return

            # Calculate elapsed time
            elapsed = time.time() - self.download_start_time

            # Calculate ETA based on percentage
            if percentage > 0 and percentage < 100:
                eta_seconds = (elapsed / percentage) * (100 - percentage)
            else:
                eta_seconds = 0

            eta_str = getTime(eta_seconds) if eta_seconds > 0 else "N/A"

            # Create status header
            stream_emoji = {"video": "🎬", "audio": "🔊", "subtitle": "📝"}.get(self.current_stream_type, "⬇️")
            task_id_str = f" [{self.task_ctx.get_short_id()}]" if self.task_ctx else ""
            status_head = (
                f"<b>{stream_emoji} Mindvalley Download{task_id_str} »</b>\n\n"
                f"<b>🎯 Stream » </b><code>{self.current_stream_type.capitalize()}</code>\n"
            )

            # Build status text with segments if available
            done_text = status_text
            if segments_done is not None and segments_total is not None:
                done_text = f"{segments_done}/{segments_total} segments"

            # Use the standard status_bar function with task_ctx (Phase 3 update)
            await status_bar(
                down_msg=status_head,
                speed=speed if speed else "N/A",  # Use parsed speed if available
                percentage=percentage,
                eta=eta_str,
                done=done_text,
                total_size="Unknown",
                engine=f"Mindvalley ({self.downloader})",
                task_ctx=self.task_ctx  # NEW: Pass task context for per-task progress
            )
        except Exception as e:
            log.warning(f"Failed to update progress bar: {e}")

    async def simple_message_update(self, text: str):
        """Simple message update for non-progress messages"""
        try:
            # Use task_ctx.status_msg if available, otherwise fall back to global MSG
            status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg
            if status_msg:
                await status_msg.edit_text(text)
        except Exception as e:
            log.warning(f"Failed to update message: {e}")
