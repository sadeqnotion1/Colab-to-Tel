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
from colab_leecher.utility.helper import sizeUnit, getTime, get_max_split_size_mib, get_bulk_pack_size_mib
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

                # yt-dlp options for TikTok matching main (1).yml pattern
                # Pattern: %(uploader|unknown_uploader)s/@%(uploader|unknown_uploader)s_%(upload_date>%Y-%m-%d|unknown_date)s_%(title).80B_%(id)s.%(ext)s
                output_template = str(Path(self.download_dir) / "%(uploader|unknown_uploader)s" / "@%(uploader|unknown_uploader)s_%(upload_date>%Y-%m-%d|unknown_date)s_%(title).80B_%(id)s.%(ext)s")

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
                    'ignoreerrors': True,
                    'no_color': True,
                    'downloader': 'aria2c',
                    'downloader_args': {
                        'aria2c': ['-x', '16', '-s', '16', '-k', '1M']
                    }
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
                    # Use the file_path returned by yt-dlp
                    file_path = result.get('file_path')

                    if file_path and os.path.exists(file_path):
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
                        error_msg = f"File not found after download: {file_path}"
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
            Dict with success status, error, and file_path if successful
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Use extract_info with download=True to get the final info dict including filename
                info = ydl.extract_info(url, download=True)
                file_path = ydl.prepare_filename(info)
                
                # Double-check existence (sometimes extensions change during post-processing)
                if not os.path.exists(file_path):
                    # Check for common extensions if the exact path doesn't exist
                    base_path = os.path.splitext(file_path)[0]
                    for ext in ['.mp4', '.mkv', '.webm', '.m4a']:
                        if os.path.exists(base_path + ext):
                            file_path = base_path + ext
                            break
                            
            meta = info or {}
            return {
                'success': True,
                'error': None,
                'file_path': file_path,
                'uploader': meta.get('uploader') or meta.get('uploader_id') or meta.get('channel') or meta.get('creator'),
                'upload_date': meta.get('upload_date'),
            }
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

    async def download_bulk(self, urls: List[str], size_limit: int = None) -> Tuple[bool, str, List[str]]:
        """
        Download multiple TikTok videos in parallel until size limit is reached.
        Enforces a hard limit to stay under the specified size.

        Args:
            urls: List of TikTok URLs to download
            size_limit: Optional maximum size in bytes for this batch

        Returns:
            Tuple of (overall_success: bool, summary_message: str, remaining_urls: List[str])
        """
        try:
            # Fix #1: size the batch limit dynamically from the user's Telegram
            # premium status (1.9 GB standard / 3.8 GB premium) instead of a
            # hardcoded 500 MB cap. A caller-provided size_limit is still honored.
            if size_limit is None:
                # Honors the user's Pack Size setting (Auto = premium-aware max).
                size_limit = get_bulk_pack_size_mib() * 1024 * 1024
                log.info(f"TikTok bulk batch limit set to {sizeUnit(size_limit)} (pack size setting)")

            self.urls = urls
            total_videos = len(urls)
            remaining_urls = []
            self.batch_user_stats = {} # Track video count per user in THIS batch
            self.batch_user_dates = {} # Fix #2: upload_date list per user in THIS batch

            log.info(f"Starting bulk download of up to {total_videos} TikTok videos (Hard Limit: {sizeUnit(size_limit)})")
            self.start_progress_tracking("video")

            # Create semaphore to limit concurrent downloads
            semaphore = asyncio.Semaphore(self.max_concurrent)

            processed_count = 0
            current_batch_size = 0
            session_successful = []
            
            # To handle hard limit accurately, we'll use a task queue approach
            # instead of fixed chunks, allowing us to stop as soon as we hit the limit
            
            pending_urls = urls.copy()
            active_tasks = set()
            last_update_time = 0
            
            while (pending_urls or active_tasks) and not (self.task_ctx and self.task_ctx.is_cancelled):
                # Start new downloads if we have room and haven't hit the limit
                while len(active_tasks) < self.max_concurrent and pending_urls:
                    # Check if we've already hit or exceeded the limit
                    if current_batch_size >= size_limit:
                        log.info(f"Hard size limit ({sizeUnit(size_limit)}) reached/exceeded. Stopping new downloads.")
                        remaining_urls = pending_urls
                        pending_urls = [] # Stop starting new ones
                        break
                    
                    url = pending_urls.pop(0)
                    video_num = total_videos - len(pending_urls) - len(active_tasks)
                    
                    task = asyncio.create_task(
                        self._download_single_video(url, video_num, total_videos, semaphore)
                    )
                    active_tasks.add(task)

                if not active_tasks:
                    break

                # Wait for at least one task to complete
                done, active_tasks = await asyncio.wait(
                    active_tasks, 
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in done:
                    result = await task
                    processed_count += 1
                    
                    if result['success']:
                        # Check if this new file would put us over the limit
                        # Even if it does, we keep it since it's already downloaded,
                        # but we won't start any more.
                        current_batch_size += result['file_size']
                        self.successful_downloads.append(result)
                        session_successful.append(result)
                        
                        # Update user stats (Fix #2: capture uploader + upload_date)
                        try:
                            uploader = result.get('uploader')
                            if not uploader:
                                parts = Path(result['file_path']).parts
                                uploader = parts[-2] if len(parts) >= 2 else 'unknown_uploader'
                            self.batch_user_stats[uploader] = self.batch_user_stats.get(uploader, 0) + 1
                            upload_date = result.get('upload_date')
                            if upload_date and str(upload_date).isdigit() and len(str(upload_date)) == 8:
                                self.batch_user_dates.setdefault(uploader, []).append(str(upload_date))
                        except Exception as e:
                            log.warning(f"Could not extract uploader for stats: {e}")
                    else:
                        self.failed_downloads.append(result)

                    # Update progress - Throttle updates to Telegram (every 3s or every 5 videos)
                    now = time.time()
                    if now - last_update_time > 3.0 or processed_count % 5 == 0 or processed_count == total_videos:
                        percentage = (processed_count / total_videos) * 90
                        status_text = f"{processed_count}/{total_videos} videos ({len(session_successful)} OK, {len(self.failed_downloads)} failed)"
                        status_text += f" | {sizeUnit(current_batch_size)}/{sizeUnit(size_limit)}"
                        
                        # Store current size for status bar
                        self.total_size = current_batch_size
                        await self.update_progress_bar(percentage, status_text, engine="TikTok Bulk", force_update=True)
                        last_update_time = now

            # Store counts in task_ctx for consolidation if available
            if self.task_ctx:
                self.task_ctx.metadata['success_count'] = len(self.successful_downloads)
                self.task_ctx.metadata['failed_count'] = len(self.failed_downloads)


                # Check if we just hit the limit after these tasks finished
                if current_batch_size >= size_limit and pending_urls:
                    log.info(f"Hard size limit ({sizeUnit(size_limit)}) hit after task completion. Remaining: {len(pending_urls)}")
                    remaining_urls.extend(pending_urls)
                    pending_urls = []

            # Summary logic...
            if self.task_ctx and self.task_ctx.is_cancelled:
                remaining_urls.extend(pending_urls)

            success_count = len(session_successful)
            fail_count = len(self.failed_downloads)

            log.info(f"Batch download complete: {success_count} succeeded, {fail_count} failed")

            if success_count == 0 and not remaining_urls:
                await self.update_progress_bar(100.0, "❌ All downloads failed", engine="TikTok Bulk")
                return False, "All downloads failed", []

            batch_total_size = sum(d['file_size'] for d in session_successful)
            summary = f"✅ Downloaded {success_count} videos ({sizeUnit(batch_total_size)})"
            if fail_count > 0:
                summary += f"\n⚠️ {fail_count} failed total"
            if remaining_urls:
                summary += f"\n⏸ {len(remaining_urls)} remaining (Limit reached)"

            await self.update_progress_bar(90.0, summary, engine="TikTok Bulk")

            return True, summary, remaining_urls

        except Exception as e:
            error_msg = f"Bulk download error: {str(e)}"
            log.exception(error_msg)
            await self.update_progress_bar(0.0, f"❌ {error_msg}", engine="TikTok Bulk")
            return False, error_msg, []

    def _sanitize_username(self, name) -> str:
        cleaned = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(name or '').lstrip('@')).strip('_')
        return cleaned or 'unknown'

    def get_batch_archive_name(self, part_num: int = 1) -> str:
        """Fix #2: descriptive archive name based on the current batch.

        - Single user with dates -> TikTok_@user_[YYYY-MM-DD_to_YYYY-MM-DD]
        - Multiple users        -> TikTok_Bulk_user1_user2_user3[_and_others]_BatchN
        """
        users = list(self.batch_user_stats.keys()) if getattr(self, 'batch_user_stats', None) else []
        if not users:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            return f"TikTok_Bulk_{timestamp}_Batch{part_num}"

        if len(users) == 1:
            raw_user = users[0]
            user = self._sanitize_username(raw_user)
            dates = sorted(
                d for d in getattr(self, 'batch_user_dates', {}).get(raw_user, [])
                if d and str(d).isdigit() and len(str(d)) == 8
            )
            if dates:
                def _fmt(d):
                    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                lo, hi = dates[0], dates[-1]
                if lo == hi:
                    return f"TikTok_@{user}_[{_fmt(lo)}]"
                return f"TikTok_@{user}_[{_fmt(lo)}_to_{_fmt(hi)}]"
            return f"TikTok_@{user}_Batch{part_num}"

        shown = [self._sanitize_username(u) for u in users[:3]]
        name = "TikTok_Bulk_" + "_".join(shown)
        if len(users) > 3:
            name += "_and_others"
        return f"{name}_Batch{part_num}"

    def get_batch_caption(self) -> str:
        """Fix #2: 'Contains videos from: @user1, @user2' for the upload caption."""
        users = list(self.batch_user_stats.keys()) if getattr(self, 'batch_user_stats', None) else []
        if not users:
            return ""
        handles = ", ".join(f"@{str(u).lstrip('@')}" for u in users)
        return f"Contains videos from: {handles}"

    def get_batch_user_summary(self) -> str:
        """
        Get a summary of users and their video counts in the CURRENT batch.

        Returns:
            HTML formatted string for Telegram caption.
        """
        if not hasattr(self, 'batch_user_stats') or not self.batch_user_stats:
            return ""

        summary = "\n\n<b>👤 Users in this Batch:</b>\n"
        # Sort users by video count descending
        sorted_users = sorted(self.batch_user_stats.items(), key=lambda x: x[1], reverse=True)
        
        for user, count in sorted_users:
            summary += f"• <code>{user}</code>: <b>{count}</b> videos\n"
        
        return summary

    def get_failed_urls_log(self) -> str:
        """
        Get a list of failed URLs and their errors as a string for a text file

        Returns:
            String content for failed_urls.txt
        """
        if not self.failed_downloads:
            return ""

        content = "TikTok Bulk Download - Failed URLs Log\n"
        content += f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        content += "=" * 40 + "\n\n"

        for failure in self.failed_downloads:
            url = failure.get('url', 'Unknown URL')
            error = failure.get('error', 'Unknown error')
            content += f"URL: {url}\n"
            content += f"Error: {error}\n"
            content += "-" * 20 + "\n"

        return content

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
            
            # Set total size for archive progress bar
            if self.task_ctx:
                self.task_ctx.transfer.total_size = self.total_size
                
            await self.update_progress_bar(95.0, "Creating ZIP archive...", engine="TikTok Bulk")

            # Use the existing archive() function from converters.py
            # Pass the download directory to archive all files in it
            # Split size follows the chosen Pack Size, but never exceeds the
            # Telegram upload limit (1.9 GB standard / 3.8 GB premium).
            max_split = min(get_bulk_pack_size_mib(), get_max_split_size_mib()) * 1024 * 1024
            archive_path, archive_size = await archive(
                path=self.download_dir,
                remove=False,  # Don't remove source files
                max_split_size_bytes=max_split,
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
