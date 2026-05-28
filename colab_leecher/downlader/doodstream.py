#copyright 2026 © theSadeQ | DoodStream Downloader for Telegram-Leecher
import logging
import re
import random
import time
from typing import Optional, Tuple
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession

from colab_leecher.utility.variables import TRANSFER, TaskError
from colab_leecher.downlader.aria2 import aria2_Download

log = logging.getLogger(__name__)


class HTTPClientSession:
    """Wrapper around curl_cffi's AsyncSession to handle Cloudflare-protected mirror domains."""
    def __init__(self, impersonate="chrome", timeout=30.0, trust_env=True):
        self.session = AsyncSession(
            impersonate=impersonate,
            timeout=timeout,
            trust_env=trust_env
        )

    async def __aenter__(self):
        await self.session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.__aexit__(exc_type, exc_val, exc_tb)

    async def get_text(self, url: str, headers: Optional[dict] = None) -> str:
        r = await self.session.get(url, headers=headers)
        r.raise_for_status()
        return r.text


class DoodStreamDownloader:
    """
    Downloader for DoodStream and its mirrors using curl_cffi Chrome impersonation
    and passing the resolved direct links to the bot's standard aria2 downloader.
    """
    def __init__(self, client=None, message=None, task_ctx=None):
        self.client = client
        self.message = message
        self.task_ctx = task_ctx

    async def download(self, url: str, index: int = 1) -> bool:
        log.info(f"[DoodStream] Resolving link {index}: {url}")
        
        embed_url = url.replace('/d/', '/e/')
        domain = urlparse(embed_url).netloc
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": embed_url
        }

        direct_url = None
        title = f"doodstream_video_{index}"

        try:
            # Step 1: Use curl_cffi with Chrome Impersonation to bypass Cloudflare
            async with HTTPClientSession() as session:
                html_content = await session.get_text(embed_url, headers=headers)
                
                pass_md5_match = re.search(r'/pass_md5/([^"\']+)', html_content)
                if not pass_md5_match:
                    raise ValueError("Could not find 'pass_md5' in the embed page.")
                
                pass_md5_path = pass_md5_match.group(1)
                pass_md5_url = f"https://{domain}/pass_md5/{pass_md5_path}"
                
                media_url_base = await session.get_text(pass_md5_url, headers=headers)
                
                token = pass_md5_path.split('/')[-1]
                random_chars = ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', k=10))
                
                direct_url = f"{media_url_base}{random_chars}?token={token}&expiry={int(time.time())}"
                
                soup = BeautifulSoup(html_content, "html.parser")
                title_tag = soup.find("title")
                if title_tag:
                    title = title_tag.text.strip()
                
                # Cleanup filename
                title = re.sub(r'[\\/*?:"<>|]', "", title)
                title = title.replace(" - DoodStream", "").strip()
                
            log.info(f"[DoodStream] Direct link resolved successfully for '{title}'")

        except Exception as e:
            error_reason = f"DoodStream resolution failed: {str(e)[:100]}"
            log.error(f"[DoodStream] Failed to resolve link {url}: {e}")
            if TaskError:
                TaskError.failed_links.append({
                    "link": url,
                    "filename": title,
                    "index": index,
                    "reason": error_reason
                })
            return False

        # Step 2: Pass the direct link to the bot's standard aria2 downloader
        # Pass the resolved title as pre_determined_name and add Referer header
        aria2_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"https://{domain}/"
        }
        
        aria2_success = False
        filename = f"{title}.mp4"
        try:
            aria2_success = await aria2_Download(
                link=direct_url,
                num=index,
                pre_determined_name=filename,
                task_ctx=self.task_ctx,
                headers=aria2_headers
            )
        except Exception as e:
            log.error(f"[DoodStream] Download via Aria2 failed: {e}")
            aria2_success = False

        if aria2_success:
            if TRANSFER:
                TRANSFER.successful_downloads.append({
                    'url': url,
                    'filename': filename
                })
            return True
        else:
            if TaskError:
                # Find if already added or add it
                if not any(f["link"] == url for f in TaskError.failed_links):
                    TaskError.failed_links.append({
                        "link": url,
                        "filename": filename,
                        "index": index,
                        "reason": "Aria2 download failed."
                    })
            return False
