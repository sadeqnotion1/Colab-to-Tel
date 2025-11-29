#================================================
#FILE: colab_leecher/downlader/terabox.py
#================================================
import aiohttp
import logging
from colab_leecher.utility.variables import Aria2c
from colab_leecher.utility.handler import cancelTask
from colab_leecher.downlader.aria2 import aria2_Download


async def terabox_download(link: str, index, task_ctx = None) -> bool: # Added return type hint and task_ctx
    global Aria2c, TaskError, log # Add TaskError, log
    payload = {"url": f"{link}"}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    fast_download_url = ""
    slow_download_url = ""
    final_url_used = ""
    success = False
    intended_filename = "Unknown Terabox File" # Placeholder

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                "https://ytshorts.savetube.me/api/v1/terabox-downloader",
                data=payload, headers=headers, timeout=30 # Add timeout
            ) as response:
                response.raise_for_status()
                json_response = await response.json()
                # <<< Get filename if available in response >>>
                intended_filename = json_response["response"][0].get("title", intended_filename)
                fast_download_url = json_response["response"][0]["resolutions"]["Fast Download"]
                slow_download_url = json_response["response"][0]["resolutions"]["HD Video"]
        except Exception as e:
            error_reason = f"Failed to get Terabox link: {str(e)[:100]}"
            log.error(f"Error getting Terabox download link for {link}: {e}")
            # <<< ADD TO FAILED LINKS >>>
            failed_info = {"link": link, "filename": intended_filename, "index": index, "reason": error_reason}
            if TaskError: TaskError.failed_links.append(failed_info)
            return False # Exit if link generation fails

        # Try Fast Download URL first
        aria2_success = False
        try:
            log.info(f"Attempting Terabox Fast Download for link index {index}")
            final_url_used = fast_download_url
            # <<< Modify aria2_Download to return True/False >>>
            aria2_success = await aria2_Download(fast_download_url, index, intended_filename, task_ctx) # Pass filename and task_ctx
        except Exception as e:
            log.warning(f"Fast download attempt failed for Terabox link {index}: {e}")
            aria2_success = False # Explicitly mark as failed

        # If Fast Download failed, try Slow Download URL
        if not aria2_success:
            log.info(f"Fast download failed, trying Terabox Slow Download for link index {index}")
            try:
                final_url_used = slow_download_url
                 # <<< Modify aria2_Download to return True/False >>>
                aria2_success = await aria2_Download(slow_download_url, index, intended_filename, task_ctx) # Pass filename and task_ctx
            except Exception as e:
                error_reason = f"Slow Terabox DL failed: {str(e)[:100]}"
                log.error(f"Slow download failed for Terabox link {index}: {e}")
                # <<< ADD TO FAILED LINKS (only if slow fails too) >>>
                failed_info = {"link": link, "filename": intended_filename, "index": index, "reason": error_reason}
                if TaskError: TaskError.failed_links.append(failed_info)
                aria2_success = False # Mark as failed

    # Check final status from aria2 attempts
    if aria2_success:
         # <<< ADD TO SUCCESSFUL DOWNLOADS >>>
         # Need the actual filename determined by aria2
         # This requires aria2_Download to return filename or update TRANSFER
         actual_filename = intended_filename # Placeholder - requires update in aria2_Download
         TRANSFER.successful_downloads.append({'url': link, 'filename': actual_filename})
         success = True
    else:
         success = False
         # Failure details should have been added by aria2_Download or the catch blocks here

    return success
