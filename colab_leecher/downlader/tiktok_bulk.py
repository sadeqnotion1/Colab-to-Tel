# copyright 2025 © theSadeQ | https://github.com/theSadeQ/Telegram-Leecher

"""
TikTok Bulk Downloader
Downloads multiple TikTok videos in parallel from a GitHub Gist URL and creates a ZIP archive
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Optional, Dict

import aiohttp
import yt_dlp
from pyrogram.types import Message

from colab_leecher.downlader.base import BaseDownloader
from colab_leecher.utility.task_context import TaskContext
from colab_leecher.utility.helper import sizeUnit, getTime
from colab_leecher.utility.converters import archive

log = logging.getLogger(__name__)


class TikTokBulkDownloader(BaseDownloader):
    """Handles bulk TikTok video downloads with parallel processing"""

    def __init__(self, client, message: Message, task_ctx: TaskContext = None):
        """
        Initialize TikTok bulk downloader

        Args:
            client: Pyrogram client instance
            message: Message that triggered the download
            task_ctx: Task context for parallel downloads
        """
        super().__init__(client, message, task_ctx)

        self.urls: List[str] = []
        self.successful_downloads: List[Dict[str, str]] = []
        self.failed_downloads: List[Dict[str, str]] = []
        self.max_concurrent = 5  # Download 5 videos at a time

        log.info(f"TikTokBulkDownloader initialized (task: {task_ctx.get_short_id() if task_ctx else 'legacy'})")

    async def fetch_gist_urls(self, gist_url: str) -> Tuple[bool, List[str]]:
        """
        Fetch TikTok URLs from a GitHub Gist

        Args:
            gist_url: GitHub Gist URL (e.g., https://gist.github.com/user/gist_id)

        Returns:
            Tuple of (success: bool, urls: List[str])
        """
        try:
            log.info(f"Fetching URLs from Gist: {gist_url}")

            # Update progress
            await self.update_progress_bar(0.0, "Fetching URLs from Gist...", engine="TikTok Bulk")

            # SECURITY: Validate Gist URL to prevent SSRF attacks
            from urllib.parse import urlparse
            parsed_url = urlparse(gist_url)

            # Only allow github gist domains
            allowed_domains = ["gist.github.com", "gist.githubusercontent.com"]
            if parsed_url.netloc not in allowed_domains:
                error_msg = f"Invalid Gist domain: {parsed_url.netloc}. Only GitHub Gists allowed."
                log.error(error_msg)
                await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
                return False, []

            # SECURITY: Reject URLs with credentials or non-standard ports
            if parsed_url.username or parsed_url.password:
                error_msg = "Gist URL must not contain credentials"
                log.error(error_msg)
                await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
                return False, []

            if parsed_url.port and parsed_url.port not in [80, 443]:
                error_msg = "Gist URL must use standard ports"
                log.error(error_msg)
                await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
                return False, []

            # Convert regular gist URL to raw URL if needed
            if "gist.github.com" in gist_url and "/raw/" not in gist_url:
                # Extract gist ID and convert to raw URL
                # Pattern: https://gist.github.com/username/gist_id
                gist_match = re.search(r'gist\.github\.com/[^/]+/([a-f0-9]+)', gist_url)
                if gist_match:
                    gist_id = gist_match.group(1)
                    raw_url = f"https://gist.githubusercontent.com/{gist_id}/raw/"
                    log.info(f"Converted to raw URL: {raw_url}")
                    gist_url = raw_url

            # Fetch the gist content
            async with aiohttp.ClientSession() as session:
                async with session.get(gist_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        error_msg = f"Failed to fetch Gist: HTTP {response.status}"
                        log.error(error_msg)
                        await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
                        return False, []

                    content = await response.text()

            # Parse URLs from content (one per line, skip empty lines and comments)
            urls = []
            for line in content.split('\n'):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#') or line.startswith('//'):
                    continue

                # Check if it's a TikTok URL
                if self._is_tiktok_url(line):
                    urls.append(line)
                else:
                    log.warning(f"Skipping non-TikTok URL: {line}")

            if not urls:
                error_msg = "No valid TikTok URLs found in Gist"
                log.error(error_msg)
                await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
                return False, []

            log.info(f"Found {len(urls)} TikTok URLs in Gist")
            await self.update_progress_bar(5.0, f"Found {len(urls)} videos", engine="TikTok Bulk")

            return True, urls

        except Exception as e:
            error_msg = f"Error fetching Gist: {str(e)}"
            log.exception(error_msg)
            await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
            return False, []

    def _is_tiktok_url(self, url: str) -> bool:
        """
        Check if URL is a valid TikTok URL

        Args:
            url: URL to check

        Returns:
            bool: True if valid TikTok URL
        """
        tiktok_patterns = [
            r'tiktok\.com',
            r'vm\.tiktok\.com',
            r'vt\.tiktok\.com',
            r'm\.tiktok\.com'
        ]

        return any(re.search(pattern, url, re.IGNORECASE) for pattern in tiktok_patterns)

    async def _download_single_video(
        self,
        url: str,
        video_num: int,
        total_videos: int,
        semaphore: asyncio.Semaphore
    ) -> Dict[str, any]:
        """
        Download a single TikTok video using yt-dlp

        Args:
            url: TikTok video URL
            video_num: Video number (for tracking)
            total_videos: Total number of videos
            semaphore: Semaphore for limiting concurrent downloads

        Returns:
            Dict with download result info
        """
        async with semaphore:
            try:
                log.info(f"Starting download {video_num}/{total_videos}: {url}")

                # Get video info first
                video_title = await self._get_video_title(url)

                # Extract username and video ID from URL for suffix
                _url_match = re.search(r'tiktok\.com/@([^/?#]+)/video/(\d+)', url)
                if _url_match:
                    _username = _url_match.group(1)
                    _video_id = _url_match.group(2)

                # Sanitize filename and build output name (no numbering prefix)
                safe_title = self._sanitize_filename(video_title)
                if _url_match:
                    output_filename = f"{_username}_{_video_id}_{safe_title}"
                else:
                    output_filename = safe_title
                output_template = str(Path(self.download_dir) / f"{output_filename}.%(ext)s")

                # yt-dlp options for TikTok
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': output_template,
                    'quiet': True,
                    'no_warnings': True,
                    'retries': 3,
                    'fragment_retries': 3,
                    'skip_unavailable_fragments': True,
                    'concurrent_fragment_downloads': 4,
                    'http_chunk_size': 10485760,  # 10MB chunks
                    'writethumbnail': False,
                    'logger': SilentLogger(),
                }

                # Download video in a thread to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None,
                    self._sync_download,
                    url,
                    ydl_opts
                )

                if result['success']:
                    # Find the downloaded file
                    file_path = self._find_downloaded_file(output_filename)

                    if file_path:
                        file_size = os.path.getsize(file_path)
                        log.info(f"✅ Downloaded {video_num}/{total_videos}: {file_path} ({sizeUnit(file_size)})")

                        return {
                            'success': True,
                            'url': url,
                            'file_path': file_path,
                            'file_size': file_size,
                            'title': video_title,
                            'video_num': video_num
                        }
                    else:
                        error_msg = "File not found after download"
                        log.error(f"❌ Video {video_num}: {error_msg}")
                        return {
                            'success': False,
                            'url': url,
                            'error': error_msg,
                            'video_num': video_num
                        }
                else:
                    log.error(f"❌ Video {video_num}: {result['error']}")
                    return {
                        'success': False,
                        'url': url,
                        'error': result['error'],
                        'video_num': video_num
                    }

            except Exception as e:
                error_msg = str(e)
                log.exception(f"Error downloading video {video_num}: {url}")
                return {
                    'success': False,
                    'url': url,
                    'error': error_msg,
                    'video_num': video_num
                }

    def _sync_download(self, url: str, ydl_opts: dict) -> Dict[str, any]:
        """
        Synchronous download function to run in thread

        Args:
            url: Video URL
            ydl_opts: yt-dlp options

        Returns:
            Dict with success status and error if any
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            return {'success': True, 'error': None}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def _get_video_title(self, url: str) -> str:
        """
        Get video title from URL using yt-dlp

        Args:
            url: Video URL

        Returns:
            Video title or "Unknown"
        """
        try:
            loop = asyncio.get_event_loop()
            title = await loop.run_in_executor(
                None,
                self._sync_get_title,
                url
            )
            return title or "Unknown"
        except Exception as e:
            log.warning(f"Failed to get video title: {e}")
            return "Unknown"

    def _sync_get_title(self, url: str) -> str:
        """Synchronous function to get video title"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'logger': SilentLogger()}) as ydl:
                info = ydl.extract_info(url, download=False)
                return info.get('title', 'Unknown')
        except Exception as e:
            log.warning(f"Error extracting title: {e}")
            return "Unknown"

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to remove invalid characters and prevent path traversal

        Args:
            filename: Original filename

        Returns:
            Sanitized filename safe for file system
        """
        # SECURITY: Prevent path traversal - replace path separators first
        filename = filename.replace('/', '_').replace('\\', '_')

        # SECURITY: Reject filenames starting with dots (hidden files/relative paths)
        filename = filename.lstrip('.')

        # Remove invalid characters
        sanitized = re.sub(r'[<>:"|?*]', '', filename)

        # Limit length (leave room for number prefix and extension)
        max_length = 100
        if len(sanitized) > max_length:
            sanitized = sanitized[:100]

        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')

        return sanitized if sanitized else "video"

    def _find_downloaded_file(self, base_filename: str) -> Optional[str]:
        """
        Find downloaded file with various possible extensions

        Args:
            base_filename: Base filename without extension

        Returns:
            Full file path if found, None otherwise
        """
        possible_extensions = ['.mp4', '.mkv', '.webm', '.mov', '.avi']

        for ext in possible_extensions:
            file_path = Path(self.download_dir) / f"{base_filename}{ext}"
            if file_path.exists():
                return str(file_path)

        return None

    async def download_bulk(self, urls: List[str]) -> Tuple[bool, str]:
        """
        Download multiple TikTok videos in parallel

        Args:
            urls: List of TikTok URLs to download

        Returns:
            Tuple of (overall_success: bool, summary_message: str)
        """
        try:
            self.urls = urls
            total_videos = len(urls)

            log.info(f"Starting bulk download of {total_videos} TikTok videos")
            self.start_progress_tracking("video")

            # Create semaphore to limit concurrent downloads
            semaphore = asyncio.Semaphore(self.max_concurrent)

            # Create download tasks
            tasks = []
            for i, url in enumerate(urls, 1):
                task = asyncio.create_task(
                    self._download_single_video(url, i, total_videos, semaphore)
                )
                tasks.append(task)

            # Process downloads with progress updates
            completed = 0
            for task in asyncio.as_completed(tasks):
                # CRITICAL: Check if task was cancelled by user
                if self.task_ctx and self.task_ctx.is_cancelled:
                    log.info(f"TikTok bulk download cancelled by user at {completed}/{total_videos} videos")
                    await self.update_progress_bar(
                        (completed / total_videos) * 95,
                        f"❌ Cancelled ({completed}/{total_videos} completed)",
                        engine="TikTok Bulk"
                    )
                    # Cancel remaining tasks
                    for remaining_task in tasks:
                        if not remaining_task.done():
                            remaining_task.cancel()
                    break

                result = await task
                completed += 1

                # Update successful/failed lists
                if result['success']:
                    self.successful_downloads.append(result)
                else:
                    self.failed_downloads.append(result)

                # Update progress
                percentage = (completed / total_videos) * 95  # Reserve 5% for zipping
                status_text = f"{completed}/{total_videos} videos ({len(self.successful_downloads)} OK, {len(self.failed_downloads)} failed)"
                await self.update_progress_bar(percentage, status_text, engine="TikTok Bulk")

            # Summary
            success_count = len(self.successful_downloads)
            fail_count = len(self.failed_downloads)

            log.info(f"Bulk download complete: {success_count} succeeded, {fail_count} failed")

            if success_count == 0:
                await self.update_progress_bar(100.0, "❌ All downloads failed", engine="TikTok Bulk")
                return False, "All downloads failed"

            # Calculate total size
            total_size = sum(d['file_size'] for d in self.successful_downloads)
            summary = f"✅ Downloaded {success_count}/{total_videos} videos ({sizeUnit(total_size)})"

            if fail_count > 0:
                summary += f"\n⚠️ {fail_count} failed"

            await self.update_progress_bar(95.0, summary, engine="TikTok Bulk")

            return True, summary

        except Exception as e:
            error_msg = f"Bulk download error: {str(e)}"
            log.exception(error_msg)
            await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
            return False, error_msg

    async def create_zip_archive(self, custom_name: str = None) -> Tuple[bool, Optional[str]]:
        """
        Create ZIP archive of downloaded videos

        Args:
            custom_name: Custom name for ZIP file (optional)

        Returns:
            Tuple of (success: bool, zip_path: Optional[str])
        """
        try:
            # Generate ZIP filename with timestamp
            if custom_name:
                zip_name = f"{custom_name}.zip"
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
                zip_name = f"TikTok_Bulk_{timestamp}.zip"

            log.info(f"Creating ZIP archive: {zip_name}")
            await self.update_progress_bar(95.0, "Creating ZIP archive...", engine="TikTok Bulk")

            # Use the existing archive() function from converters.py
            # Pass the download directory to archive all files in it
            # CRITICAL: Enable ZIP splitting to prevent Telegram 2GB upload limit issues
            archive_path, archive_size = await archive(
                path=self.download_dir,
                remove=False,  # Don't remove source files
                max_split_size_bytes=1900*1024*1024,  # 1.9GB per part (Telegram limit: 2GB)
                task_ctx=self.task_ctx
            )

            if archive_path:
                log.info(f"ZIP created: {archive_path} ({sizeUnit(archive_size)})")
                await self.update_progress_bar(100.0, f"✅ ZIP ready ({sizeUnit(archive_size)})", engine="TikTok Bulk")
                return True, archive_path
            else:
                log.error("ZIP creation failed")
                await self.update_progress_bar(95.0, "❌ ZIP creation failed", engine="TikTok Bulk")
                return False, None

        except Exception as e:
            error_msg = f"Error creating ZIP: {str(e)}"
            log.exception(error_msg)
            await self.update_progress_bar(95.0, f"❌ {error_msg}", engine="TikTok Bulk")
            return False, None

    def get_failed_report(self) -> str:
        """
        Generate a report of failed downloads

        Returns:
            Formatted string with failed download details
        """
        if not self.failed_downloads:
            return "All videos downloaded successfully!"

        report = f"⚠️ Failed Downloads ({len(self.failed_downloads)}):\n\n"

        for failure in self.failed_downloads:
            video_num = failure['video_num']
            url = failure['url']
            error = failure.get('error', 'Unknown error')

            # Truncate URL for readability
            short_url = url[:50] + "..." if len(url) > 50 else url

            report += f"{video_num}. {short_url}\n"
            report += f"   Error: {error}\n\n"

        return report


class SilentLogger:
    """Silent logger for yt-dlp to suppress output"""

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        if "ERROR" in msg:
            log.error(f"yt-dlp: {msg}")
