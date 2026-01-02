# /content/Telegram-Leecher-Gemini/colab_leecher/utility/helper.py
import os
import math
import psutil
import logging
import pathlib
import asyncio
import re
import aiohttp 
import asyncio 
import urllib.parse
import time
from time import time
from PIL import Image
from os import path as ospath
from datetime import datetime
import mimetypes
from urllib.parse import urlparse, unquote
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram import enums
from pyrogram.errors import MessageNotModified
from .variables import BOT, MSG, BotTimes, Messages, Paths, TRANSFER
from .task_context import TaskContext  # NEW: Import for multi-task support

# Setup logger
log = logging.getLogger(__name__)

async def get_video_metadata(file_path: str) -> dict:
    """
    Extracts video metadata (duration, width, height) using ffprobe.
    Returns a dict with keys: duration, width, height.
    """
    metadata = {"duration": 0, "width": 0, "height": 0}
    if not os.path.exists(file_path):
        return metadata

    try:
        cmd = [
            "ffprobe", 
            "-v", "error", 
            "-select_streams", "v:0", 
            "-show_entries", "stream=width,height,duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", 
            file_path
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20)
        
        if process.returncode == 0 and stdout:
            # Output format depends on ffprobe version/file, typically lines like:
            # 1280
            # 720
            # 120.5
            lines = stdout.decode().strip().splitlines()
            # We don't know the order guaranteed by select_streams without specific -of json, 
            # but usually it matches requested order or simply values.
            # A safer way is using json output, but let's try a more robust csv/json approach or simple parsing.
            
            # Re-run with specific json format for reliability
            cmd_json = [
                "ffprobe", 
                "-v", "error", 
                "-select_streams", "v:0", 
                "-show_entries", "stream=width,height,duration", 
                "-of", "json", 
                file_path
            ]
            process_json = await asyncio.create_subprocess_exec(
                *cmd_json,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout_json, _ = await asyncio.wait_for(process_json.communicate(), timeout=20)
            
            if process_json.returncode == 0 and stdout_json:
                import json
                try:
                    data = json.loads(stdout_json.decode())
                    if "streams" in data and len(data["streams"]) > 0:
                        stream = data["streams"][0]
                        metadata["width"] = int(stream.get("width", 0))
                        metadata["height"] = int(stream.get("height", 0))
                        # Duration might be in format or stream
                        dur = stream.get("duration")
                        if dur:
                            metadata["duration"] = int(float(dur))
                        else:
                            # Try format duration if stream duration missing
                            cmd_fmt = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", file_path]
                            proc_fmt = await asyncio.create_subprocess_exec(*cmd_fmt, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                            out_fmt, _ = await proc_fmt.communicate()
                            if out_fmt:
                                data_fmt = json.loads(out_fmt.decode())
                                if "format" in data_fmt:
                                    metadata["duration"] = int(float(data_fmt["format"].get("duration", 0)))
                except Exception as json_err:
                    log.warning(f"Failed to parse ffprobe JSON: {json_err}")

    except Exception as e:
        log.warning(f"Error getting video metadata: {e}")
    
    return metadata

async def get_video_duration(file_path: str, ffprobe_timeout: int = 20, ffmpeg_timeout: int = 30) -> int:
    """
    Tries to get video duration using ffprobe, with a fallback to parsing ffmpeg output.
    Now wraps get_video_metadata for ffprobe part.
    """
    # Try the robust metadata function first
    meta = await get_video_metadata(file_path)
    if meta["duration"] > 0:
        return meta["duration"]
        
    duration = 0
    log.debug(f"Attempting fallback duration extraction for: {os.path.basename(file_path)}")


    # --- Method 2: ffmpeg (Fallback) ---
    log.debug(f"ffprobe failed or timed out. Trying ffmpeg fallback (timeout: {ffmpeg_timeout}s)...")
    try:
        ffmpeg_cmd = ["ffmpeg", "-i", file_path]
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE # ffmpeg outputs info to stderr
        )
        # We only need stderr for duration, stdout is not needed
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=ffmpeg_timeout)

        stderr_str = stderr.decode(errors='ignore')
        log.debug(f"ffmpeg stderr output captured (length: {len(stderr_str)}).") # Avoid logging potentially huge output

        # Parse duration from stderr (e.g., "Duration: 00:01:35.24, ...")
        duration_match = re.search(r"Duration:\s*(\d{2,}):(\d{2}):(\d{2})\.(\d{2})", stderr_str)
        if duration_match:
            hours = int(duration_match.group(1))
            minutes = int(duration_match.group(2))
            seconds = int(duration_match.group(3))
            # Milliseconds (group 4) usually not needed for Telegram duration (integer)
            duration = hours * 3600 + minutes * 60 + seconds
            log.info(f"Duration extracted via ffmpeg fallback: {duration}s for {os.path.basename(file_path)}")
            return duration
        else:
            log.warning(f"Could not parse duration from ffmpeg output for {os.path.basename(file_path)}.")
            # Log a snippet of stderr for debugging if parsing failed
            log.debug(f"ffmpeg stderr snippet: {stderr_str[:500]}...")


    except asyncio.TimeoutError:
        log.warning(f"ffmpeg timed out after {ffmpeg_timeout}s for {os.path.basename(file_path)}.")
        try:
            process.kill()
            await process.wait()
        except ProcessLookupError: pass
        except Exception as kill_err: log.warning(f"Error killing timed-out ffmpeg: {kill_err}")
    except FileNotFoundError:
        log.error("ffmpeg command not found. Cannot use fallback duration extraction.")
        # Return 0 as we can't fall back
    except Exception as e:
        log.error(f"Error running ffmpeg for duration for {os.path.basename(file_path)}: {e}", exc_info=False)

    log.warning(f"All methods failed to get duration for {os.path.basename(file_path)}. Returning 0.")
    return 0 # Return 0 if all methods failed

# You might also want a separate function for thumbnail generation
# If 'thumbMaintainer' does both, you'll need to split its logic
# or create a new function like this (implementation details depend
# on how thumbMaintainer currently works):

async def get_video_thumbnail(file_path: str, output_dir: str = "/tmp", timeout: int = 45) -> str | None:
    """
    Generates a thumbnail for a video file using ffmpeg.

    Args:
        file_path: Path to the video file.
        output_dir: Directory to save the thumbnail.
        timeout: Timeout in seconds for ffmpeg.

    Returns:
        Path to the generated JPEG thumbnail, or None on failure.
    """
    base_name = os.path.basename(file_path)
    # Ensure the generated thumbnail name is filesystem-safe
    safe_base_name = "".join([c if c.isalnum() or c in ('-', '_') else '_' for c in os.path.splitext(base_name)[0]])
    thumb_name = safe_base_name + ".jpg"
    thumb_path = os.path.join(output_dir, thumb_name)

    # Ensure output directory exists
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as e:
        log.error(f"Could not create thumbnail output directory {output_dir}: {e}")
        return None

    # --- Corrected Indentation for Cleanup ---
    # Delete existing thumbnail if it exists to ensure freshness
    if os.path.exists(thumb_path):
        try:
            os.remove(thumb_path)
        except OSError as e:
            log.warning(f"Could not remove existing thumbnail {thumb_path}: {e}")
    # --- End Corrected Indentation ---

    log.debug(f"Attempting thumbnail generation for: {base_name} (timeout: {timeout}s)")
    ffmpeg_cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", # Suppress unnecessary output
        "-ss", "5", # Seek to 5 seconds (or choose another time)
        "-i", file_path,
        "-vframes", "1", # Extract only one frame
        "-vf", "scale=320:-1", # Scale width to 320px, height proportional (-1)
        "-q:v", "3", # Quality (2-5 is often good)
        "-y", # Overwrite output without asking
        thumb_path
    ]

    process = None # Define process variable outside try block
    try:
        process = await asyncio.create_subprocess_exec(
            *ffmpeg_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

        if process.returncode == 0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            log.info(f"Thumbnail generated successfully: {thumb_path}")
            # Optional: Convert to JPEG just in case ffmpeg output format wasn't exactly JPEG
            try:
                # Assuming convertIMG is defined in the same file or imported correctly
                converted_path = convertIMG(thumb_path)
                if converted_path and os.path.exists(converted_path):
                    log.debug(f"Thumbnail converted/verified as JPEG: {converted_path}")
                    return converted_path
                elif os.path.exists(thumb_path):
                     log.warning(f"convertIMG failed for {thumb_path}, returning original ffmpeg output.")
                     return thumb_path # Return original if conversion failed but file exists
                else:
                     log.error(f"convertIMG failed and original thumb {thumb_path} missing.")
                     return None # Conversion failed and removed original
            except NameError:
                 log.warning("convertIMG function not found, skipping conversion check.")
                 return thumb_path # Return original path if convertIMG doesn't exist
            except Exception as convert_err:
                 log.error(f"Error during convertIMG for {thumb_path}: {convert_err}")
                 if os.path.exists(thumb_path):
                     return thumb_path # Return original if conversion errorred
                 else:
                     return None
        else:
            stderr_str = stderr.decode(errors='ignore').strip()
            log.error(f"ffmpeg thumbnail generation failed for {base_name}. Code: {process.returncode}, Stderr: {stderr_str}")
            # --- Corrected Indentation for Cleanup ---
            if os.path.exists(thumb_path):
                try:
                    os.remove(thumb_path)
                except OSError as remove_err:
                    log.warning(f"Could not remove failed thumbnail {thumb_path}: {remove_err}")
            # --- End Corrected Indentation ---
            return None

    except asyncio.TimeoutError:
        log.warning(f"ffmpeg thumbnail generation timed out after {timeout}s for {base_name}.")
        if process: # Check if process was created before trying to kill
             try:
                 process.kill()
                 await process.wait()
             except ProcessLookupError: pass # Process already finished
             except Exception as kill_err: log.warning(f"Error killing timed-out ffmpeg (thumb): {kill_err}")
        # --- Corrected Indentation for Cleanup ---
        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError as remove_err:
                log.warning(f"Could not remove timed-out thumbnail {thumb_path}: {remove_err}")
        # --- End Corrected Indentation ---
        return None
    except FileNotFoundError:
        log.error("ffmpeg command not found. Cannot generate thumbnail.")
        return None
    except Exception as e:
        log.error(f"Error generating thumbnail for {base_name}: {e}", exc_info=True) # Log full traceback here
        # --- Corrected Indentation for Cleanup ---
        if os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except OSError as remove_err:
                log.warning(f"Could not remove error-state thumbnail {thumb_path}: {remove_err}")
        # --- End Corrected Indentation ---
        return None

# --- Filename & URL Utilities ---

def clean_filename(filename):
    """Removes potentially problematic characters and returns None on failure."""
    if not filename or not isinstance(filename, str):
        # Return None if input is None, empty, or not a string
        return None
    try:
        # Decode URL encoding
        decoded_name = urllib.parse.unquote(str(filename), encoding='utf-8', errors='replace')
    except Exception as e:
        log.warning(f"URL decode error in clean_filename for '{filename}': {e}")
        decoded_name = str(filename) # Use original if decoding fails

    # Remove forbidden characters and leading/trailing junk
    # Explicitly remove ".." path traversal attempts
    decoded_name = decoded_name.replace('..', '__')

    # Remove control characters \x00-\x1f
    cleaned = re.sub(r'[\\/:*?"<>|]+|[\x00-\x1f]', '_', decoded_name).strip('._ -')

    # Limit length (e.g., 240 characters)
    cleaned = cleaned[:240]

    # Return None if cleaning results in an empty string
    return cleaned if cleaned else None
# --- End clean_filename function ---

async def extract_filename_from_url(url: str) -> str | None:
    """
    Extract filename from URL using IDM-like approach.
    Returns None on failure.
    """
    # Uses clean_filename defined elsewhere in helper.py
    global log # Assuming log = logging.getLogger(__name__) is defined globally in helper.py

    log.debug(f"Attempting filename extraction for URL: {url}")

    if not isinstance(url, str) or not url.lower().startswith(('http://', 'https://')):
        log.warning(f"Invalid URL format: {str(url)[:100]}")
        return None

    # Common browser headers
    browser_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': '*/*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': url,
        'DNT': '1', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1', 'Cache-Control': 'max-age=0',
    }

    # It will now use the clean_filename defined at the module level in helper.py

    # Helper function to extract filename from Content-Disposition header
    def extract_from_content_disposition(content_disposition):
        # This inner function now relies on the main clean_filename from helper.py
        if not content_disposition: return None
        log.info(f"Found Content-Disposition header: {content_disposition}")
        # Try filename*= format (RFC 5987)
        match_utf8 = re.search(r"filename\*=(?:UTF-8|utf-8)''([^;]+)", content_disposition, re.IGNORECASE)
        if match_utf8:
            filename_raw = match_utf8.group(1); log.debug(f"Raw filename from UTF-8*: '{filename_raw}'")
            try:
                decoded = urllib.parse.unquote(filename_raw, encoding='utf-8', errors='replace')
                cleaned = clean_filename(decoded) # Use outer clean_filename
                if cleaned: log.info(f"Using filename from Content-Disposition (filename*): {cleaned}"); return cleaned
            except Exception as e: log.warning(f"Error decoding filename* value: {e}")

        # Try alternative UTF-8 pattern with single quotes
        match_utf8_alt = re.search(r"filename\*=UTF-8''([\w%.-]+)", content_disposition, re.IGNORECASE)
        if match_utf8_alt:
            filename_raw = match_utf8_alt.group(1); log.debug(f"Raw filename from UTF-8* alt: '{filename_raw}'")
            cleaned = clean_filename(urllib.parse.unquote(filename_raw, encoding='utf-8', errors='replace'))
            if cleaned: log.info(f"Using filename from Content-Disposition (UTF-8* alt): {cleaned}"); return cleaned

        # Standard filename="xxx" format
        match_std = re.search(r'filename="([^"]+)"', content_disposition, re.IGNORECASE)
        if match_std:
            filename_raw = match_std.group(1); log.debug(f"Raw filename from standard quotes: '{filename_raw}'")
            try:
                # Try decoding as UTF-8 first, then latin-1 -> utf-8 as fallback
                decoded_std = urllib.parse.unquote(filename_raw, encoding='utf-8', errors='replace')
                cleaned_std = clean_filename(decoded_std)

                decoded_alt = None
                try: # Nested try for latin-1 decode, as it can fail
                     decoded_alt = filename_raw.encode('latin-1').decode('utf-8', errors='replace')
                except Exception: pass # Ignore if this specific decode fails
                cleaned_alt = clean_filename(decoded_alt) if decoded_alt else None

                # Prefer alt if it's different, valid, and has no replacement chars (?)
                if cleaned_alt and cleaned_alt != cleaned_std and '?' not in cleaned_alt:
                    log.debug(f"Using standard decoded Latin1->UTF8: {cleaned_alt}"); return cleaned_alt
                elif cleaned_std: # Otherwise use standard UTF-8 decode if valid
                    log.debug(f"Using standard decoded: {cleaned_std}"); return cleaned_std
                # If both fail or result in None after cleaning, we proceed
            except Exception as e: log.warning(f"Error decoding standard Content-Disposition: {e}")

        # Plain filename=xxx format (no quotes)
        match_plain = re.search(r'filename=([^;"\s]+)', content_disposition, re.IGNORECASE)
        if match_plain:
            filename_raw = match_plain.group(1); log.debug(f"Raw filename from plain format: '{filename_raw}'")
            cleaned = clean_filename(urllib.parse.unquote(filename_raw, encoding='utf-8', errors='replace'))
            if cleaned: log.info(f"Using filename from Content-Disposition (plain): {cleaned}"); return cleaned
        return None

    # --- HEAD and GET Requests COMMENTED OUT ---
    # # 1. Try HEAD request
    # log.debug(f"Attempting HEAD request for {url}...")
    # head_content_type = None # Store content type from HEAD if possible
    # try:
    #     async with aiohttp.ClientSession() as session:
    #          async with session.head(url, headers=browser_headers, timeout=15, allow_redirects=True) as response:
    #             log.info(f"HEAD request for {url} completed with status: {response.status}")
    #             if response.status < 400:
    #                 head_content_type = response.headers.get('Content-Type', '').lower() # Store content type
    #                 content_disposition = response.headers.get('Content-Disposition')
    #                 filename = extract_from_content_disposition(content_disposition)
    #                 if filename: return filename
    #                 # Check Content-Type for clues (if no Content-Disposition)
    #                 if head_content_type and '/' in head_content_type and not head_content_type.startswith(('text/html', 'application/xhtml')):
    #                     log.debug(f"HEAD Content-type ({head_content_type}) suggests direct file. Trying path extraction early.")
    #                     parsed_url_head = urllib.parse.urlparse(str(response.url)) # Use final URL after redirects
    #                     path_head = urllib.parse.unquote(parsed_url_head.path, encoding='utf-8', errors='replace')
    #                     if path_head and '/' in path_head:
    #                         basename_head = os.path.basename(path_head.strip('/'))
    #                         if basename_head and '.' in basename_head and not basename_head.startswith('.'):
    #                              cleaned_head = clean_filename(basename_head)
    #                              if cleaned_head: log.info(f"Using filename from path (HEAD content-type hint): {cleaned_head}"); return cleaned_head
    # except Exception as head_err: log.warning(f"HEAD request failed for {url}: {head_err}")
    #
    # # 2. Try GET request
    # log.debug(f"Attempting GET request for {url}...")
    # get_content_type = None # Store content type from GET
    # try:
    #     async with aiohttp.ClientSession() as session:
    #          # Only read headers and a small part of body, don't download full file!
    #          async with session.get(url, headers=browser_headers, timeout=20, allow_redirects=True) as response:
    #             log.info(f"GET request for {url} completed with status: {response.status}")
    #             if response.status < 400:
    #                  get_content_type = response.headers.get('Content-Type', '').lower() # Store content type
    #                  # Try Content-Disposition header again (sometimes only present on GET)
    #                  content_disposition = response.headers.get('Content-Disposition')
    #                  filename = extract_from_content_disposition(content_disposition)
    #                  if filename: return filename
    #
    #                  # For HTML responses, try to extract title
    #                  if get_content_type.startswith(('text/html', 'application/xhtml')):
    #                      try:
    #                          html_content = await response.content.read(65536) # Read up to 64KB
    #                          html_str = html_content.decode('utf-8', errors='replace')
    #                          title_match = re.search(r'<title[^>]*>(.*?)</title>', html_str, re.IGNORECASE | re.DOTALL)
    #                          if title_match:
    #                              title = title_match.group(1).strip()
    #                              if title:
    #                                  title_clean = clean_filename(title)
    #                                  if title_clean:
    #                                      # Append .html if no other extension likely
    #                                      if not re.search(r'\.[a-zA-Z0-9]{2,5}$', title_clean): title_clean += '.html'
    #                                      log.info(f"Using filename from HTML title: {title_clean}")
    #                                      return title_clean
    #                      except Exception as html_err: log.warning(f"Failed to extract HTML title: {html_err}")
    # except Exception as get_err: log.warning(f"GET request failed for {url}: {get_err}")
    # --- END OF COMMENTED OUT BLOCKS ---

    # --- !!! CORRECTED INDENTATION STARTS HERE !!! ---
    # 3. Parse URL path (use original url as final_url_str since requests are disabled)
    log.debug("Falling back to URL Path extraction...")
    final_url_str = url # Use original URL as requests are disabled
    try:
        parsed_url = urllib.parse.urlparse(final_url_str)
        path_decoded = urllib.parse.unquote(parsed_url.path, encoding='utf-8', errors='replace')
        filename_from_path = os.path.basename(path_decoded.strip('/'))
        if filename_from_path and '.' in filename_from_path and not filename_from_path.startswith('.'):
            name_part, ext_part = os.path.splitext(filename_from_path)
            if name_part and ext_part: # Ensure both name and extension exist
                cleaned_from_path = clean_filename(filename_from_path)
                if cleaned_from_path:
                    log.info(f"Using filename from URL Path: {cleaned_from_path}")
                    return cleaned_from_path
    except Exception as path_err:
        log.warning(f"Error parsing URL path: {path_err}")

    # 4. Try Query Parameters
    log.debug("Trying Query Parameter extraction...")
    try:
        parsed_url = urllib.parse.urlparse(final_url_str) # Use final URL
        query_params = urllib.parse.parse_qs(parsed_url.query)
        # Expanded list of common filename parameters
        filename_params = [
            'filename', 'file', 'name', 'title', 'fn', 'download', 'id', 'attachment',
            'f', 'document', 'doc', 'pdf', 'media', 'video', 'audio', 'track',
            'image', 'img', 'photo', 'picture', 'source', 'src', 'destination',
            'output', 'out', 'export', 'path', 'target'
        ]
        for param in filename_params:
            if param in query_params and query_params[param][0]:
                param_value = query_params[param][0]
                # Basic check for validity (length, extension)
                if len(param_value) > 3 and '.' in param_value:
                    cleaned = clean_filename(urllib.parse.unquote(param_value, encoding='utf-8', errors='replace'))
                    if cleaned:
                        log.info(f"Using filename from Query Parameter ('{param}'): {cleaned}")
                        return cleaned
    except Exception as query_err:
        log.warning(f"Error parsing query parameters: {query_err}")

    # 5. Try URL fragment
    log.debug("Trying URL fragment extraction...")
    try:
        parsed_url = urllib.parse.urlparse(final_url_str) # Use final URL
        if parsed_url.fragment:
            fragment = urllib.parse.unquote(parsed_url.fragment, encoding='utf-8', errors='replace')
            # Check if fragment looks like a filename (has extension, doesn't start with .)
            if '.' in fragment and not fragment.startswith('.'):
                cleaned = clean_filename(fragment)
                if cleaned:
                    log.info(f"Using filename from URL fragment: {cleaned}")
                    return cleaned
    except Exception as frag_err:
        log.warning(f"Error parsing URL fragment: {frag_err}")

    # 6. Domain + path/timestamp as last resort
    log.debug("Using domain+path/timestamp as last resort...")
    try:
        parsed_url = urllib.parse.urlparse(final_url_str) # Use final URL
        domain = parsed_url.netloc.split(':')[0].replace("www.", "") # Remove www. and port
        path_parts = [p for p in parsed_url.path.split('/') if p]
        path_part = path_parts[-1] if path_parts else '' # Get last non-empty path part
        fallback_name = "unknown_download" # Default base

        if domain:
             # Prefer domain + last path part if it's somewhat meaningful
             if path_part and len(path_part) > 2 and not path_part.startswith('.'):
                 fallback_name = f"{domain}_{path_part}"
             else: # Otherwise use domain + timestamp
                 fallback_name = f"{domain}_{int(time.time())}"
        else: # If no domain (e.g., local file URI?), use timestamp
             fallback_name = f"download_{int(time.time())}"

        # Try to guess extension (content_type will be '' here as requests are disabled)
        content_type = '' # get_content_type or head_content_type or '' # Set to empty
        ext = mimetypes.guess_extension(content_type.split(';')[0].strip()) # This likely returns None
        if ext:
            fallback_name += ext
        # Add a default extension if none was guessed and none exists in the fallback name
        elif not re.search(r'\.[a-zA-Z0-9]+$', fallback_name):
             fallback_name += ".bin" # Default binary extension

        cleaned = clean_filename(fallback_name)
        if cleaned:
            log.info(f"Using fallback generated name: {cleaned}")
            return cleaned
    except Exception as fallback_err:
        log.warning(f"Error creating fallback filename: {fallback_err}")

    # If absolutely ALL methods failed
    log.error(f"Failed to extract any valid filename for URL: {url}")
    return None # Return None on complete failure


# --- End of function ---
    # 1. Try HEAD request for Content-Disposition header first (fast)
    log.debug(f"Attempting HEAD request for {url}...")
    try:
        async with aiohttp.ClientSession() as session:
             async with session.head(url, headers=browser_headers, timeout=15, allow_redirects=True) as response:
                log.info(f"HEAD request for {url} completed with status: {response.status}")
                
                # Check if successful
                if response.status < 400:
                    # Try Content-Disposition header
                    content_disposition = response.headers.get('Content-Disposition')
                    filename = extract_from_content_disposition(content_disposition)
                    if filename:
                        return filename
                        
                    # Also check Content-Type for clues (like PDFs)
                    content_type = response.headers.get('Content-Type', '').lower()
                    if content_type and '/' in content_type and not content_type.startswith(('text/html', 'application/xhtml')):
                        log.debug(f"Found content-type: {content_type}")
                        # This is likely a direct file download, use path extraction
                        parsed_url = urllib.parse.urlparse(url)
                        path = urllib.parse.unquote(parsed_url.path, encoding='utf-8', errors='replace')
                        if path and '/' in path:
                            basename = os.path.basename(path)
                            if basename and '.' in basename and not basename.startswith('.'):
                                cleaned = clean_filename(basename)
                                if cleaned: 
                                    log.info(f"Using filename from path (content-type hint): {cleaned}")
                                    return cleaned

    except Exception as head_err:
        log.warning(f"HEAD request failed for {url}: {head_err}")

    # 2. Try GET request (some servers only set headers on actual GET)
    log.debug(f"Attempting GET request for {url}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=browser_headers, timeout=15, allow_redirects=True) as response:
                log.info(f"GET request for {url} completed with status: {response.status}")
                
                # Try Content-Disposition header again
                content_disposition = response.headers.get('Content-Disposition')
                filename = extract_from_content_disposition(content_disposition)
                if filename:
                    return filename
                
                # For HTML responses, try to extract title as filename
                content_type = response.headers.get('Content-Type', '').lower()
                if content_type.startswith(('text/html', 'application/xhtml')):
                    try:
                        # Read first chunk to check for <title> tag (limit to avoid large downloads)
                        html_content = await response.content.read(50000)  # Read ~50KB
                        html_str = html_content.decode('utf-8', errors='replace')
                        
                        # Extract title
                        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_str, re.IGNORECASE | re.DOTALL)
                        if title_match:
                            title = title_match.group(1).strip()
                            if title:
                                # Clean and ensure it has an extension for HTML
                                title_clean = clean_filename(title)
                                if title_clean:
                                    if not title_clean.lower().endswith(('.html', '.htm')):
                                        title_clean += '.html'
                                    log.info(f"Using filename from HTML title: {title_clean}")
                                    return title_clean
                    except Exception as html_err:
                        log.warning(f"Failed to extract HTML title: {html_err}")
                
    except Exception as get_err:
        log.warning(f"GET request failed for {url}: {get_err}")

    # 3. Parse URL path
    log.debug("Falling back to URL Path extraction...")
    try:
        parsed_url = urllib.parse.urlparse(url)
        path_decoded = urllib.parse.unquote(parsed_url.path, encoding='utf-8', errors='replace')
        filename_from_path = os.path.basename(path_decoded.strip('/'))
        
        # Check if this looks like a valid filename with extension
        if filename_from_path and '.' in filename_from_path and not filename_from_path.startswith('.'):
            name_part, ext_part = os.path.splitext(filename_from_path)
            if name_part and ext_part:  # Ensure both parts exist
                cleaned_from_path = clean_filename(filename_from_path)
                if cleaned_from_path:
                    log.info(f"Using filename from URL Path: {cleaned_from_path}")
                    return cleaned_from_path
    except Exception as path_err:
        log.warning(f"Error parsing URL path for filename: {path_err}")

    # 4. Try Query Parameters - extended to check more possible parameter names
    log.debug("Trying Query Parameter extraction...")
    try:
        parsed_url = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Common parameters that might contain filenames (expanded from original)
        filename_params = [
            'filename', 'file', 'name', 'title', 'fn', 'download', 'id', 'attachment',
            'f', 'document', 'doc', 'pdf', 'media', 'video', 'audio', 'track',
            'image', 'img', 'photo', 'picture', 'source', 'src', 'destination',
            'output', 'out', 'export', 'path', 'target'
        ]
        
        for param in filename_params:
            if param in query_params and query_params[param][0]:
                param_value = query_params[param][0]
                # Skip very short or unlikely filename values
                if len(param_value) > 3 and '.' in param_value:
                    cleaned = clean_filename(urllib.parse.unquote(param_value, encoding='utf-8', errors='replace'))
                    if cleaned:
                        log.info(f"Using filename from Query Parameter ('{param}'): {cleaned}")
                        return cleaned
    except Exception as query_err:
        log.warning(f"Error parsing query parameters for filename: {query_err}")

    # 5. Try URL fragment (after #)
    log.debug("Trying URL fragment extraction...")
    try:
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.fragment:
            fragment = urllib.parse.unquote(parsed_url.fragment, encoding='utf-8', errors='replace')
            # Only use if it looks like a filename (has extension)
            if '.' in fragment and not fragment.startswith('.'):
                cleaned = clean_filename(fragment)
                if cleaned:
                    log.info(f"Using filename from URL fragment: {cleaned}")
                    return cleaned
    except Exception as frag_err:
        log.warning(f"Error parsing URL fragment for filename: {frag_err}")

    # 6. Domain + path slugified as last resort
    log.debug("Using domain+path as last resort...")
    try:
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.split(':')[0]  # Remove port if present
        
        # Get last meaningful path segment
        path_parts = [p for p in parsed_url.path.split('/') if p]
        path_part = path_parts[-1] if path_parts else ''
        
        if domain:
            if path_part and len(path_part) > 2 and not path_part.startswith('.'):
                # Use domain + path segment
                fallback_name = f"{domain}-{path_part}"
            else:
                # Just domain + timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                fallback_name = f"{domain}-{timestamp}"
                
            # Add appropriate extension based on Content-Type if we did a GET
            if 'content_type' in locals() and content_type:
                ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
                if ext:
                    fallback_name += ext
                elif fallback_name.endswith(('.html', '.htm')):
                    pass  # Already has extension
                else:
                    fallback_name += '.html'  # Default to HTML
                    
            cleaned = clean_filename(fallback_name)
            if cleaned:
                log.info(f"Using fallback domain+path name: {cleaned}")
                return cleaned
    except Exception as fallback_err:
        log.warning(f"Error creating fallback filename: {fallback_err}")

    # If ALL methods failed
    log.error(f"Failed to extract a valid filename using any method for URL: {url}")
    return None

def apply_dot_style(filename):
    """Replaces common separators with dots and cleans up."""
    # Replace spaces, underscores, hyphens, plus signs with dots
    styled_name = re.sub(r'[ _\-\+]+', '.', filename)
    # Remove brackets
    styled_name = styled_name.replace('[', '').replace(']', '')
    # Reduce multiple dots to single dots
    styled_name = re.sub(r'\.+', '.', styled_name)
    # Remove leading/trailing dots
    styled_name = styled_name.strip('.')
    return styled_name if styled_name else "styled_file"

def shortFileName(path):
    """Shortens a filename or path string if it exceeds a limit."""
    limit = 60 # Maximum length for the name part
    if not isinstance(path, str):
        return path

    if ospath.isfile(path) or ospath.isdir(path):
        dir_part, name_part = ospath.split(path)
        if not name_part: # Handle case where path ends with '/'
            return path
        if len(name_part) > limit:
            if ospath.isfile(path):
                # Preserve extension when shortening files
                base, ext = ospath.splitext(name_part)
                ext_len = len(ext)
                # Ensure at least 1 character for the base name if there's an extension
                max_base_len = max(1, limit - ext_len - 1) if ext_len > 0 else limit
                name_part = base[:max_base_len] + ext
            else:
                # Shorten directories directly
                name_part = name_part[:limit]
            return ospath.join(dir_part, name_part)
        else:
            # No shortening needed
            return path
    else:
        # If it's just a string, not a path, shorten directly
        return path[:limit] if len(path) > limit else path

def applyCustomName(task_ctx: TaskContext = None):
    """Renames the downloaded file/folder if a custom name is set and applicable.

    Args:
        task_ctx: Optional TaskContext for multi-task support
    """
    global BOT, Paths, Messages

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        log.info(f"applyCustomName() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        log.info("applyCustomName() using global state (single-task mode)")

    if _bot.Options.custom_name and _bot.Mode.type not in ["zip", "undzip"]:
        try:
            # Ensure download path exists
            if not ospath.isdir(_paths.down_path):
                log.warning(f"Cannot apply custom name: Download path '{_paths.down_path}' does not exist or is not a directory.")
                return

            items = os.listdir(_paths.down_path)
            if len(items) == 1:
                # Only apply if exactly one item exists in the download folder
                current_path = ospath.join(_paths.down_path, items[0])
                cleaned_custom_name = clean_filename(_bot.Options.custom_name)
                new_path = ospath.join(_paths.down_path, cleaned_custom_name)

                if current_path != new_path:
                    os.rename(current_path, new_path)
                    log.info(f"Applied custom name: '{items[0]}' -> '{cleaned_custom_name}'")
                    _messages.download_name = cleaned_custom_name # Update message context
                else:
                    log.info("Custom name is the same as the current name, no rename needed.")
            elif len(items) > 1:
                log.warning(f"Custom name not applied: Multiple items found in '{_paths.down_path}'.")
            else: # len(items) == 0
                log.warning(f"Custom name not applied: Path '{_paths.down_path}' is empty.")
        except Exception as e:
            log.error(f"Error applying custom name: {e}", exc_info=True)

# --- Link Type Checkers ---

def isLink(_, __, update):
    """Checks if the message text is likely a downloadable link or path."""
    text = getattr(update, 'text', None)
    if text:
        text = str(text)
        # Allow commands and local paths starting with / or ~ (for dir-leech etc.)
        if text.startswith("/") or text.startswith("~"):
            return True
        # Check for magnet links
        elif text.startswith("magnet:?xt=urn:btih:"):
            return True
        # Check for standard URL formats
        try:
            parsed = urlparse(text)
            # Requires a scheme (http, https, ftp, etc.) AND a netloc (domain name)
            if parsed.scheme and parsed.netloc:
                return True
        except ValueError:
            # Not a parseable URL
            log.debug(f"Could not parse text as URL: {text[:50]}...")
            return False
    return False

def is_google_drive(link):
    """Checks if the link is likely a Google Drive link."""
    return isinstance(link, str) and "drive.google.com" in link

def is_mega(link):
    """Checks if the link is likely a Mega.nz link."""
    return isinstance(link, str) and "mega.nz" in link

def is_m3u8_url(url):
    """
    Checks if the URL is a valid M3U8 playlist URL.

    Args:
        url: URL string to check

    Returns:
        bool: True if URL appears to be an M3U8 playlist
    """
    if not isinstance(url, str):
        return False

    # Check if URL contains .m3u8
    if '.m3u8' not in url.lower():
        return False

    # Validate URL format
    try:
        parsed = urlparse(url)
        # Must have scheme (http/https) and domain
        if parsed.scheme in ('http', 'https') and parsed.netloc:
            return True
    except ValueError:
        return False

    return False

def is_mindvalley_url(url):
    """
    Checks if the URL is from Mindvalley domain.

    Args:
        url: URL string to check

    Returns:
        bool: True if URL is from Mindvalley
    """
    if not isinstance(url, str):
        return False

    mindvalley_domains = ['mindvalley.com', 'otfp.mindvalley.com']
    return any(domain in url.lower() for domain in mindvalley_domains)

def is_terabox(link):
    """Checks if the link is likely a Terabox link."""
    return isinstance(link, str) and ("terabox" in link or "1024tera" in link)

def is_instagram(link):
    """
    Checks if the link is an Instagram link.
    Supports posts, reels, stories, IGTV, and profile links.

    Args:
        link: URL string to check

    Returns:
        bool: True if URL is from Instagram
    """
    if not isinstance(link, str):
        return False

    instagram_patterns = [
        'instagram.com',
        'instagr.am',
        'ig.me'
    ]

    return any(pattern in link.lower() for pattern in instagram_patterns)

def is_nzbcloud(link):
    """
    Checks if the link is an NZBcloud link.
    Supports files.nzbcloud.com play/download URLs.

    Args:
        link: URL string to check

    Returns:
        bool: True if URL is from NZBcloud
    """
    if not isinstance(link, str):
        return False

    nzbcloud_patterns = [
        'files.nzbcloud.com/api/v1/files/',  # Direct file URLs
        'app.nzbcloud.com',                  # App URLs
    ]

    return any(pattern in link.lower() for pattern in nzbcloud_patterns)

def is_ytdl_link(link: str) -> bool:
    if not isinstance(link, str):
        return False

    # Basic scheme check (http or https)
    if not (link.startswith("http://") or link.startswith("https://")):
        return False

    try:
        parsed_url = urlparse(link)
        # Decode percent-encoded characters in the path (e.g., %20 for space)
        path = unquote(parsed_url.path)

        # CHECK 1: Does the link end with .m3u8? (Case-insensitive)
        if path.lower().endswith(".m3u8"):
            return True # Yes, treat as YTDL link

        # CHECK 2: Is it from a common video site domain?
        domain = parsed_url.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:] # Remove www. for easier matching

        common_ytdl_domains = [
            "youtube.com", "youtube-nocookie.com", "youtu.be",
            "youtu.be", "vimeo.com", "dailymotion.com",
            "twitter.com", "facebook.com", "instagram.com",
            "tiktok.com", "soundcloud.com", "twitch.tv",
            "bitchute.com", "rumble.com",
            "mindvalley.com" # For Mindvalley pages
        ]

        for ytdl_domain in common_ytdl_domains:
            if ytdl_domain in domain:
                return True # Yes, treat as YTDL link

    except Exception:
        # If any error occurs during parsing (e.g., invalid URL format)
        return False 

    return False # If none of the checks passed



def is_telegram(link):
    """Checks if the link is likely a Telegram message link."""
    return isinstance(link, str) and "t.me/" in link

def is_torrent(link):
    """Checks if the link is a magnet link or a .torrent file URL."""
    return isinstance(link, str) and (
        "magnet:?xt=urn:btih:" in link or link.lower().endswith(".torrent")
    )

# --- Size, Time & Type Utilities ---

def getTime(seconds):
    """Formats seconds into a human-readable d/h/m/s string."""
    try:
        # Check if seconds is non-numeric, infinite or NaN before conversion
        if not isinstance(seconds, (int, float)) or math.isinf(seconds) or math.isnan(seconds):
            return "N/A" # Return 'N/A' for invalid inputs

        seconds = int(float(seconds)) # Proceed with conversion if it's a finite number
    except (ValueError, TypeError, OverflowError): # Catch potential errors during conversion too
        return "N/A" # Handle invalid input

    if seconds < 0:
        return "N/A" # Handle negative input

    days, seconds = divmod(seconds, 24 * 3600)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    # Always show seconds if non-zero, or if it's the only unit (even if 0s)
    if seconds > 0 or not parts:
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s" # Return "0s" if calculation somehow results in empty list
# --- END FIX ---
def sizeUnit(size):
    """Formats bytes into a human-readable size string (KiB, MiB, GiB, etc.)."""
    try:
        size = float(size)
    except (ValueError, TypeError):
        return "N/A" # Handle invalid input

    if size <= 0:
        return "0 B"

    units = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    # Calculate the power of 1024
    power = math.floor(math.log(size, 1024)) if size > 0 else 0
    # Ensure the unit index stays within the bounds of the list
    unit_index = min(power, len(units) - 1)

    # Calculate the value in the chosen unit and format
    return f"{size / (1024**unit_index):.2f} {units[unit_index]}"

def getSize(path):
    """Calculates the total size of a file or directory."""
    if not isinstance(path, str) or not ospath.exists(path):
        log.warning(f"getSize: Path invalid or does not exist: {path}")
        return 0

    if ospath.isfile(path):
        try:
            return ospath.getsize(path)
        except OSError as e:
            log.error(f"getSize error (file) {path}: {e}")
            return 0
    elif ospath.isdir(path):
        total_size = 0
        try:
            for dirpath, _, filenames in os.walk(path):
                for f in filenames:
                    fp = ospath.join(dirpath, f)
                    # Skip broken symlinks
                    if ospath.islink(fp):
                        continue
                    # Add size of regular files
                    if ospath.isfile(fp):
                        try:
                            total_size += ospath.getsize(fp)
                        except OSError as e:
                            # Log error for individual file but continue calculation
                            log.error(f"getSize error (sub-file) {fp}: {e}")
        except OSError as e:
            # Error during directory traversal
            log.error(f"getSize error (dir walk) {path}: {e}")
            return 0 # Return 0 if directory walk fails
        return total_size

def fileType(file_path: str):
    """Determines the general file type based on extension."""
    # Mapping of general types to sets of lowercase extensions
    ext_map = {
        "video": {".mp4", ".avi", ".mkv", ".m2ts", ".mov", ".ts", ".m3u8", ".webm", ".mpg", ".mpeg", ".mpeg4", ".vob", ".m4v", ".wmv", ".flv"},
        "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus"},
        "photo": {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff", ".heic", ".heif"},
        # Add more types like "archive" if needed: {".zip", ".rar", ".7z", ".tar", ".gz"}
    }

    _, extension = ospath.splitext(file_path)
    ext_lower = extension.lower()

    for type_name, extensions in ext_map.items():
        if ext_lower in extensions:
            return type_name

    # Default to "document" if no match found
    return "document"

def videoExtFix(file_path: str):
    """Renames video files to .mp4 if they have other common video extensions."""
    if fileType(file_path) != "video":
        return file_path # Only process video files

    dir_path, f_name = ospath.split(file_path)
    name, ext = ospath.splitext(f_name)

    # Don't rename if already mp4 or mkv (common containers)
    if ext.lower() in ['.mp4', '.mkv']:
        return file_path

    # Rename to .mp4
    new_path = ospath.join(dir_path, name + ".mp4")
    try:
        os.rename(file_path, new_path)
        log.info(f"Renamed video '{f_name}' to '{name}.mp4'")
        return new_path
    except OSError as e:
        log.error(f"Failed rename video {file_path} to mp4: {e}")
        return file_path # Return original path on failure

def speedETA(start_time, done_bytes, total_bytes):
    """Calculates download/upload speed and Estimated Time Remaining."""
    # --- FIX: Handle datetime object for start_time ---
    if isinstance(start_time, datetime):
        start_timestamp = start_time.timestamp()
    elif isinstance(start_time, (int, float)):
        start_timestamp = start_time
    else:
        log.warning(f"speedETA received unexpected start_time type: {type(start_time)}. Using current time.")
        start_timestamp = time() # Fallback, though this might skew results

    elapsed_time = time() - start_timestamp
    # --- END FIX ---

    percentage = 0
    speed = 0
    eta = float('inf') # Default ETA is infinity

    # Calculate percentage
    if total_bytes > 0:
        percentage = min(100, (done_bytes / total_bytes) * 100)

    # Calculate speed (ensure elapsed_time is positive to avoid ZeroDivisionError)
    if done_bytes > 0 and elapsed_time > 0:
        speed = done_bytes / elapsed_time

    # Calculate ETA
    if speed > 0 and total_bytes > 0 and done_bytes < total_bytes:
        eta = max(0, (total_bytes - done_bytes) / speed) # Ensure ETA is not negative

    speed_string = f"{sizeUnit(speed)}/s" if speed > 0 else "N/A"

    return speed_string, eta, percentage


def isTimeOver(interval=2.5):
    """Checks if a specified time interval has passed since the last check."""
    global BotTimes
    now = time()
    if now - BotTimes.current_time >= interval:
        BotTimes.current_time = now # Update last check time
        return True
    return False

# --- Thumbnail Management ---

def convertIMG(image_path):
    """Converts an image to JPEG format if it isn't already."""
    if not image_path or not ospath.exists(image_path):
        return None
    try:
        with Image.open(image_path) as image:
            output_path = ospath.splitext(image_path)[0] + ".jpg"

            # If already JPEG, check if extension needs fixing
            if image.format == "JPEG":
                if image_path != output_path:
                    try:
                        # Rename to ensure .jpg extension
                        os.rename(image_path, output_path)
                        return output_path
                    except OSError as e:
                        log.warning(f"Could not rename {image_path} to {output_path}: {e}")
                        return image_path # Return original if rename fails
                else:
                    return image_path # Already JPEG with correct extension

            # Convert if not JPEG
            log.info(f"Converting {ospath.basename(image_path)} [{image.format}] to JPEG.")
            # Handle transparency (convert RGBA to RGB)
            if image.mode == 'RGBA':
                # Create a white background image
                bg = Image.new("RGB", image.size, (255, 255, 255))
                bg.paste(image, mask=image.split()[3]) # Paste using alpha channel as mask
                rgb_im = bg
            elif image.mode != 'RGB':
                # Convert other modes (like P, L) to RGB
                rgb_im = image.convert('RGB')
            else:
                rgb_im = image # Already RGB

            rgb_im.save(output_path, "JPEG", quality=95)

            # Remove original file if conversion created a new one
            if image_path != output_path:
                try:
                    os.remove(image_path)
                except OSError:
                    pass
            return output_path

    except Exception as e:
        log.error(f"Error converting image {image_path}: {e}")
        return None

# Function to check if a file is a split part
def is_split_file(filename):
    """Check if a file is a split part based on common patterns."""
    # Check for common split file patterns like .001, .002, etc. or .part1, .part2, etc.
    # Also check for .z01, .zip.001 etc.
    return bool(re.search(r'\.(part\d+|[0-9]{3,}|z[0-9]{2,}|zip\.\d+)$', filename.lower()))

# Add a timeout wrapper for thumbMaintainer
async def thumbMaintainer_with_timeout(file_path, timeout=60): # Increased default timeout slightly
    """Run thumbMaintainer with a timeout to prevent hanging"""
    global log # Ensure log is accessible
    try:
        # Run thumbMaintainer in a separate thread with timeout
        # This assumes thumbMaintainer is NOT an async function itself
        # If thumbMaintainer IS async, you'd await it directly within asyncio.wait_for
        log.debug(f"Running thumbMaintainer in executor for: {ospath.basename(file_path)} with timeout {timeout}s")
        loop = asyncio.get_event_loop()
        # Use partial to pass arguments to the synchronous thumbMaintainer function
        func_call = partial(thumbMaintainer, file_path)
        result = await asyncio.wait_for(
            loop.run_in_executor(None, func_call), # Run the sync function in default executor
            timeout=timeout
        )
        log.debug(f"thumbMaintainer completed successfully for: {ospath.basename(file_path)}")
        return result
    except asyncio.TimeoutError:
        log.warning(f"thumbMaintainer timed out after {timeout}s for: {ospath.basename(file_path)}")
        return Paths.DEFAULT_HERO, 0  # Return default values on timeout
    except Exception as e:
        # Catch other potential errors during execution
        log.error(f"Error executing thumbMaintainer_with_timeout for {ospath.basename(file_path)}: {e}", exc_info=True)
        return Paths.DEFAULT_HERO, 0 # Return defaults on other errors too

async def setThumbnail(message):
    """Downloads and sets the message photo as the custom thumbnail."""
    global BOT, Paths, MSG
    try:
        # Ensure thumbnail directory exists
        thumb_dir = ospath.dirname(Paths.THMB_PATH)
        if thumb_dir: os.makedirs(thumb_dir, exist_ok=True)

        # Remove existing thumbnail file if it exists
        if ospath.exists(Paths.THMB_PATH):
            try: os.remove(Paths.THMB_PATH)
            except OSError as e: log.warning(f"Could not remove old thumbnail file: {e}")

        # Check if message contains a photo or an image document
        photo = message.photo or (message.document and message.document.mime_type.startswith("image/"))
        if not photo:
            raise ValueError("Message does not contain a photo or image document.")

        # Download the image
        await message.download(file_name=Paths.THMB_PATH)
        if not ospath.exists(Paths.THMB_PATH):
            raise Exception("Thumbnail download failed (file not found after download call).")

        # Convert to JPEG if necessary
        converted_path = convertIMG(Paths.THMB_PATH)
        if not converted_path or not ospath.exists(converted_path):
             # If conversion failed but original download exists, maybe try using that?
             # Or just fail here. Let's fail for simplicity.
             raise Exception("Thumbnail processing/conversion failed.")
        # If conversion created a different path (e.g., .png -> .jpg), update THMB_PATH conceptually
        # (though convertIMG should handle renaming/replacing)

        BOT.Setting.thumbnail = True
        log.info("Custom thumbnail set successfully.")

        # Update status message thumbnail if a task is ongoing
        if BOT.State.task_going and MSG.status_msg:
            try:
                from pyrogram.types import InputMediaPhoto # Import locally
                await MSG.status_msg.edit_media(
                    InputMediaPhoto(Paths.THMB_PATH), # Use the final path
                    reply_markup=keyboard() # Keep cancel button
                )
            except Exception as edit_e:
                log.warning(f"Failed update status msg thumb: {edit_e}")

        return True
    except Exception as e:
        BOT.Setting.thumbnail = False # Ensure setting is false on error
        log.error(f"Error setting thumbnail: {e}", exc_info=False)
        # Clean up potentially downloaded/partially converted file
        if ospath.exists(Paths.THMB_PATH):
             try: os.remove(Paths.THMB_PATH)
             except OSError: pass
        # Also try removing potential .jpg if conversion failed mid-way?
        jpg_path = ospath.splitext(Paths.THMB_PATH)[0] + ".jpg"
        if jpg_path != Paths.THMB_PATH and ospath.exists(jpg_path):
             try: os.remove(jpg_path)
             except OSError: pass
        return False

# --- Status, UI & System Info ---

def sysINFO():
    """Returns a string containing system CPU, RAM, and Disk usage."""
    global Messages
    try:
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/") # Assumes root ('/') is the relevant disk
        cpu = psutil.cpu_percent() # Gets average CPU usage since last call or over interval

        ram_used = sizeUnit(ram.used)
        ram_total = sizeUnit(ram.total)
        ram_perc = f"{ram.percent}%"
        disk_used = sizeUnit(disk.used)
        disk_total = sizeUnit(disk.total)
        disk_perc = f"{disk.percent}%"
        cpu_perc = f"{cpu:.1f}%" # Format CPU to one decimal place

        # Construct the info string
        info = (
            f"\n\n<b>├⚙️ CPU »</b> <i>{cpu_perc}</i>"
            f"\n<b>├💾 RAM »</b> <i>{ram_used} / {ram_total} ({ram_perc})</i>"
            f"\n<b>╰💿 DISK »</b> <i>{disk_used} / {disk_total} ({disk_perc})</i>"
            + Messages.caution_msg # Append caution message if it exists
        )
        return info
    except Exception as e:
        log.warning(f"Could not get system info: {e}")
        return "" # Return empty string on error

def keyboard(task_id: str = None):
    """
    Returns the standard cancel button keyboard.

    Args:
        task_id: Optional task ID for multi-task cancellation.
                 If provided, callback_data="cancel:{task_id}"
                 If None, callback_data="cancel" (legacy single-task mode)
    """
    import logging
    log = logging.getLogger(__name__)

    # pyrogram imports moved to top
    if task_id:
        # Multi-task mode: include task_id in callback data
        callback_data = f"cancel:{task_id}"
        log.info(f"🔍 keyboard() called with task_id='{task_id}' | callback_data='{callback_data}' | length={len(callback_data)}")
    else:
        # Legacy mode: simple cancel
        callback_data = "cancel"
        log.info(f"🔍 keyboard() called with NO task_id | callback_data='cancel'")

    return InlineKeyboardMarkup([[InlineKeyboardButton("Cancel ❌", callback_data=callback_data)]])

async def message_deleter(message1, message2):
    """Deletes one or two messages, ignoring errors."""
    delete_tasks = []
    for msg in [message1, message2]:
        if msg and hasattr(msg, 'delete'):
            # Create delete coroutine task
            delete_tasks.append(msg.delete())

    if delete_tasks:
        # Run delete tasks concurrently and ignore exceptions
        results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                # Log ignored exceptions if needed, but don't stop execution
                log.warning(f"Message delete failed (ignored): {result}")

async def send_settings(client, message, msg_id, is_command: bool):
    """Sends or edits the settings message."""
    global BOT
    # Determine current upload mode and the callback for the opposite mode
    up_mode_display = "Media" if BOT.Options.stream_upload else "Document"
    next_up_mode_action = "document" if BOT.Options.stream_upload else "media"

    # Create keyboard layout
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Upload As: {up_mode_display}", callback_data=next_up_mode_action),
         InlineKeyboardButton("Video Settings", callback_data="video")],
        [InlineKeyboardButton("Caption Font", callback_data="caption"),
         InlineKeyboardButton("Thumbnail", callback_data="thumb")],
        [InlineKeyboardButton("Set Suffix", callback_data="set-suffix"),
         InlineKeyboardButton("Set Prefix", callback_data="set-prefix")],
        [InlineKeyboardButton("Close ✘", callback_data="close")],
    ])

    # Build the settings text
    text = "**SETTINGS ⚙️ »**"
    text += f"\n\nUPLOAD » <i>{BOT.Setting.stream_upload}</i>"
    text += f"\nSPLIT » <i>{BOT.Setting.split_video}</i>"
    text += f"\nCONVERT » <i>{BOT.Setting.convert_video}</i>"
    text += f"\nCAPTION » <i>{BOT.Setting.caption}</i>"

    pr = "Exists" if BOT.Setting.prefix else "None"
    su = "Exists" if BOT.Setting.suffix else "None"
    thmb = "Exists" if BOT.Setting.thumbnail else "None"
    text += f"\nPREFIX » <i>{pr}</i>\nSUFFIX » <i>{su}</i>"
    text += f"\nTHUMBNAIL » <i>{thmb}</i>"

    # Display cookie status
    cf_set = "Set" if BOT.Setting.nzb_cf_clearance else "Not Set"
    bitso_id_set = "Set" if BOT.Setting.bitso_identity_cookie else "Not Set"
    bitso_sess_set = "Set" if BOT.Setting.bitso_phpsessid_cookie else "Not Set"
    text += f"\n\n<b>Cookies:</b>"
    text += f"\n🍪 NZB CF » <i>{cf_set}</i>"
    text += f"\n🍪 Bitso ID » <i>{bitso_id_set}</i>"
    text += f"\n🍪 Bitso Sess » <i>{bitso_sess_set}</i>"

    try:
        if is_command:
            # Send as a new reply if triggered by /settings command
            await message.reply_text(text=text, reply_markup=keyboard)
        else:
            # Edit the existing message if triggered by a callback
            await client.edit_message_text(
                chat_id=message.chat.id,
                message_id=msg_id,
                text=text,
                reply_markup=keyboard
            )
    except Exception as error:
        # Avoid logging "message is not modified" errors
        if "Message is not modified" not in str(error):
            log.error(f"Settings display error: {error}", exc_info=False)

# (Inside colab_leecher/utility/helper.py)

async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine, use_custom_text: bool = False, task_ctx: TaskContext = None):
    """
    Update progress bar for download/upload tasks.

    Args:
        task_ctx: Optional TaskContext for per-task state (NEW in Phase 3)
                  If provided, uses task_ctx.status_msg and task_ctx.started_at
                  If None, falls back to global MSG and BotTimes (backward compat)
    """
    global MSG, Messages, BotTimes, log # Ensure necessary globals are accessible

    # Debug logging added as requested
    task_id_str = f"[{task_ctx.get_short_id()}]" if task_ctx else "[legacy]"
    log.info(f"📊 status_bar {task_id_str} called. Pct={percentage}%, Speed={speed}")

    # ===== PARALLEL MODE: Skip individual status updates, use dashboard instead =====
    if task_ctx:
        from .task_context import TASK_QUEUE
        if await TASK_QUEUE.has_task(task_ctx.task_id):
            # Task is in parallel queue - individual status updates are disabled
            # Update transfer stats for dashboard to read, but don't edit Telegram message
            try:
                # Parse size string to bytes for dashboard to detect download progress
                done_bytes = 0
                if ' GiB' in done:
                    done_bytes = int(float(done.replace(' GiB', '').strip()) * 1024 * 1024 * 1024)
                elif ' MiB' in done:
                    done_bytes = int(float(done.replace(' MiB', '').strip()) * 1024 * 1024)
                elif ' KiB' in done:
                    done_bytes = int(float(done.replace(' KiB', '').strip()) * 1024)
                elif ' B' in done:
                    done_bytes = int(float(done.replace(' B', '').strip()))

                task_ctx.transfer.down_bytes = done_bytes

                # Also update speed for dashboard display
                task_ctx.transfer.last_speed = speed
            except (ValueError, AttributeError) as e:
                task_ctx.transfer.down_bytes = 1  # Set to non-zero to indicate download started
                log.warning(f"Failed to parse download size '{done}': {e}")
            log.debug(f"⏩ status_bar {task_id_str}: Parallel mode - Updated stats: {done} ({task_ctx.transfer.down_bytes} bytes), speed: {speed}")
            return
    # ===== END PARALLEL MODE CHECK =====

    # Throttle updates using per-task timing (parallel-safe) or global timing (legacy)
    current_time = time()
    if task_ctx:
        # Multi-task mode: Use per-task timer (parallel-safe!)
        if current_time - task_ctx.last_status_update < 2.5:
            log.info(f"⏸️ status_bar {task_id_str}: Throttled (per-task timer), skipping.")
            return
        task_ctx.last_status_update = current_time
        log.info(f"✅ status_bar {task_id_str}: Timer OK, will update Telegram message")
    else:
        # Legacy single-task mode: Use global timer
        if not isTimeOver(2.5):
            log.info(f"⏸️ status_bar {task_id_str}: Throttled (global timer), skipping.")
            return
        log.info(f"✅ status_bar {task_id_str}: Global timer OK, will update")

    # NEW: Use task_ctx.status_msg if available, otherwise fall back to global MSG
    status_msg = task_ctx.status_msg if task_ctx else MSG.status_msg

    if status_msg and hasattr(status_msg, 'edit_text'):
        final_text = ""
        try:
            if use_custom_text:
                # Using custom text (likely from 7z archive progress)
                log.debug("status_bar using custom text mode.")
                # Assumes down_msg is the full pre-formatted text from the caller
                final_text = down_msg + sysINFO() # Append system info
            else:
                # Standard formatting mode
                log.debug("status_bar using standard formatting mode.")
                bar_length = 12 # Length of the progress bar

                # Ensure percentage is treated as a number for calculation
                try:
                    percentage_float = float(percentage)
                except (ValueError, TypeError):
                    log.warning(f"status_bar received invalid percentage type: {percentage}. Defaulting to 0.")
                    percentage_float = 0.0

                # Calculate filled part of the bar
                filled_length = min(bar_length, max(0, int(percentage_float / 100 * bar_length)))
                # Create the bar string (Corrected variable name from previous analysis)
                bar = "█" * filled_length + "░" * (bar_length - filled_length)

                eta_str = eta # Use eta string passed directly

                # NEW: Calculate elapsed time from task_ctx if available, otherwise use global
                if task_ctx and task_ctx.started_at:
                    elapsed_seconds = (datetime.now() - task_ctx.started_at).seconds
                else:
                    elapsed_seconds = (datetime.now() - BotTimes.task_start).seconds
                elapsed_str = getTime(elapsed_seconds)

                # Format the main body of the status message
                text_body = (f"\n╭「{bar}」 **»** __{percentage_float:.1f}%__" # Display percentage with one decimal
                             f"\n├⚡️ **Speed »** **{str(speed)}**"
                             f"\n├⚙️ **Engine »** **{str(engine)}**"
                             f"\n├⏳ **ETA »** __{eta_str}__"
                             f"\n├⏱️ **Elapsed »** __{elapsed_str}__"
                             f"\n├✅ **Done »** **{str(done)}**"
                             f"\n╰📦 **Total »** __{str(total_size)}__")

                # Combine the header (down_msg), body, and system info
                final_text = down_msg + text_body + sysINFO()

            # --- Edit the Telegram message ---
            kb_markup = keyboard(task_ctx.get_short_id()) if task_ctx else keyboard() # Get the cancel keyboard with task ID
            log.debug(f"Attempting to edit status message {status_msg.id}")

            # Check if message is a photo (has thumbnail) or plain text
            if hasattr(status_msg, 'photo') and status_msg.photo:
                # Message has a photo/thumbnail - edit caption to preserve thumbnail
                await status_msg.edit_caption(caption=final_text, reply_markup=kb_markup, parse_mode=enums.ParseMode.HTML)
                log.debug(f"Status message caption edited (thumbnail preserved).")
            else:
                # Plain text message - edit text normally
                await status_msg.edit_text(text=final_text, disable_web_page_preview=True, reply_markup=kb_markup, parse_mode=enums.ParseMode.HTML)
                log.debug(f"Status message text edited.")

        except MessageNotModified:
            # This is expected if the message content hasn't changed, ignore it silently
            log.debug("Status message content hasn't changed, skipping edit.")
            pass
        except Exception as e:
            # Log other errors during message editing
            if "Message to edit not found" not in str(e): # Avoid logging if message was deleted
                log.warning(f"Status bar update failed: {str(e)}")

    else:
         # Log if the status message object is missing or invalid
         if not status_msg:
             log.debug(f"status_bar {task_id_str}: status_msg is not set.")
         elif not hasattr(status_msg, 'edit_text'):
             log.debug(f"status_bar {task_id_str}: status_msg object lacks 'edit_text' method.")
            
def multipartArchive(path: str, archive_type: str, remove_parts: bool):
    """Calculates total size of a multipart archive and optionally removes parts."""
    dirname, filename = ospath.split(path)
    name, _ = ospath.splitext(filename) # Get base name without the first extension
    part_counter = 1
    total_size = 0
    base_name_for_log = name # Default base name for logging/return
    deleted_files_list = [] # List to store paths of parts to delete

    log.debug(f"Checking multipart archive: type={archive_type}, path={path}")

    try:
        if archive_type == "rar":
            # Handle RAR naming convention (e.g., name.part01.rar, name.part001.rar)
            base_part_name = name.split(".part")[0] if ".part" in name else name
            base_name_for_log = base_part_name # Update log name
            while True:
                found_part_this_iteration = False
                # Check for different padding lengths (part1, part01, part001)
                for pad in [1, 2, 3]:
                    part_name = f"{base_part_name}.part{str(part_counter).zfill(pad)}.rar"
                    part_path = ospath.join(dirname, part_name)
                    if ospath.exists(part_path):
                        total_size += getSize(part_path)
                        if remove_parts: deleted_files_list.append(part_path)
                        found_part_this_iteration = True
                        break # Found the part for this number, move to next
                if found_part_this_iteration:
                    part_counter += 1
                else:
                    break # No more parts found for this base name

        elif archive_type == "7z":
            # Handle 7z naming (e.g., name.7z.001, name.7z.002)
            while True:
                part_name = f"{name}.{str(part_counter).zfill(3)}" # Assumes .001, .002 format
                part_path = ospath.join(dirname, part_name)
                if ospath.exists(part_path):
                    total_size += getSize(part_path)
                    if remove_parts: deleted_files_list.append(part_path)
                    part_counter += 1
                else:
                    break
            # Remove the .001 extension part from the base name if present
            if base_name_for_log.lower().endswith(".001"):
                base_name_for_log, _ = ospath.splitext(base_name_for_log)


        elif archive_type == "zip":
            # Handle zip multipart (e.g., name.zip, name.z01, name.z02)
            # First, check for the main .zip file itself (might exist even if split)
            main_zip_path = ospath.join(dirname, f"{name}.zip")
            if ospath.exists(main_zip_path):
                # Only add size if it wasn't the triggering path? Or always add?
                # Let's assume the trigger 'path' is one of the parts.
                # We need the size of all parts including .zip if it exists.
                # This section needs care to avoid double counting.
                # Let's recalculate the size based on found parts.
                total_size = 0 # Reset size calculation for zip
                deleted_files_list = [] # Reset delete list

                # Add size of .zip file if it exists
                if ospath.exists(main_zip_path):
                    total_size += getSize(main_zip_path)
                    if remove_parts: deleted_files_list.append(main_zip_path)

                # Check for .zXX parts
                while True:
                    part_name = f"{name}.z{str(part_counter).zfill(2)}"
                    part_path = ospath.join(dirname, part_name)
                    if ospath.exists(part_path):
                        total_size += getSize(part_path)
                        if remove_parts: deleted_files_list.append(part_path)
                        part_counter += 1
                    else:
                        break
                # Remove the .zip from the base name if it exists
                if base_name_for_log.lower().endswith(".zip"):
                    base_name_for_log, _ = ospath.splitext(base_name_for_log)

    except Exception as e:
        log.error(f"Error processing multipart archive {path}: {e}", exc_info=True)

    # Perform deletion if requested
    if remove_parts and deleted_files_list:
        log.info(f"Removing {len(deleted_files_list)} archive parts for '{base_name_for_log}'...")
        for f_to_del in deleted_files_list:
            try:
                if ospath.exists(f_to_del):
                    os.remove(f_to_del)
            except OSError as e:
                # Log warning but continue trying to delete others
                log.warning(f"Could not remove part {f_to_del}: {e}")

    log.debug(f"Multipart check result: name='{base_name_for_log}', total_size={total_size}")
    return base_name_for_log, total_size

# --- YTDL Completion Check ---
def isYtdlComplete():
    """Checks if any yt-dlp temporary files remain in the download directory."""
    global Paths
    try:
        # Check if the main download path exists and is a directory
        if not ospath.isdir(Paths.down_path):
            log.warning(f"isYtdlComplete check: Download path '{Paths.down_path}' not found or not a directory.")
            # If the path doesn't exist, assume download didn't start or failed cleanly
            return True

        # Walk through the directory and check for temp files
        for _, _, filenames in os.walk(Paths.down_path):
            for f in filenames:
                # Check for common yt-dlp temporary extensions
                if f.lower().endswith((".part", ".ytdl", ".tmp")):
                    log.debug(f"YTDL temporary file found: {f}. Download not complete.")
                    return False # Found a temp file, download is not complete

        # No temporary files found
        log.debug("No YTDL temporary files found. Download assumed complete.")
        return True
    except Exception as e:
        log.error(f"Error checking YTDL completion: {e}")
        # Be cautious on error: assume not complete? Or complete?
        # Let's assume *not* complete if we can't check properly.
        return False
# Add this function, e.g., at the end of utility/helper.py OR within __main__.py

async def fetch_links_from_url(url: str) -> list[str] | None:
    """
    Fetches content from supported raw text URLs and parses valid links ONLY.
    Ignores any filename information.
    Returns list of links, empty list if no links found, or None on error/unsupported URL.
    """
    log = logging.getLogger(__name__)
    import re # Local import just in case
    import aiohttp # Local import just in case

    log.debug(f"fetch_links_from_url called with URL: {url}")
    raw_url = None
    cleaned_url = url.strip()
    is_recognized_source = False

    # --- URL Recognition Logic ---
    if "pastebin.com" in cleaned_url:
        match = re.match(r"https?://pastebin\.com/raw/(\w+)", cleaned_url)
        if match: raw_url = cleaned_url; is_recognized_source = True
        else:
            match = re.match(r"https?://pastebin\.com/(\w+)", cleaned_url)
            if match: raw_url = f"https://pastebin.com/raw/{match.group(1)}"; is_recognized_source = True
    elif "gist.githubusercontent.com" in cleaned_url and "/raw" in cleaned_url:
         raw_url = cleaned_url; is_recognized_source = True
    elif "rentry.co" in cleaned_url:
        match = re.match(r"https?://rentry\.co/(\w+)", cleaned_url.split('/raw')[0])
        if match: raw_url = f"https://rentry.co/{match.group(1)}/raw"; is_recognized_source = True
    elif "pastes.io" in cleaned_url:
        match = re.match(r"https?://pastes\.io/raw/(\w+)", cleaned_url)
        if match: raw_url = cleaned_url; is_recognized_source = True
        else:
            match = re.match(r"https?://pastes\.io/(\w+)", cleaned_url)
            if match: raw_url = f"https://pastes.io/raw/{match.group(1)}"; is_recognized_source = True
    elif "pastie.org" in cleaned_url:
        match = re.match(r"https?://pastie\.org/p/([\w-]+)/raw", cleaned_url)
        if match: raw_url = cleaned_url; is_recognized_source = True
    elif cleaned_url.lower().startswith(('http://', 'https://')) and cleaned_url.lower().endswith(".txt"):
         raw_url = cleaned_url; is_recognized_source = True

    if not raw_url:
        log.debug(f"URL not recognized as a supported raw link source: {cleaned_url}")
        return None # Return None if not supported type

    log.info(f"Attempting to fetch links from detected raw URL: {raw_url}")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(raw_url, timeout=25) as response:
                response.raise_for_status()
                text_content = await response.text()
                if not text_content: return []

                links = []
                filenames = []  # NEW: Store TITLE= filenames
                pending_filename = None  # NEW: Track filename for next URL
                valid_link_pattern = re.compile(r"^(https?://|magnet:\?|ftps?://)")

                for line_raw in text_content.splitlines():
                    line = line_raw.strip().split('|')[0].strip() # Get part before | if exists
                    if line == "---": break # Stop if separator found

                    # NEW: Check for TITLE= lines (NZBCloud format)
                    if line.startswith("TITLE="):
                        pending_filename = line[6:].strip()  # Extract filename after "TITLE="
                        log.debug(f"Found TITLE filename: {pending_filename}")
                        continue

                    if valid_link_pattern.match(line):
                        links.append(line)
                        # NEW: Associate the pending filename with this link
                        if pending_filename:
                            filenames.append(pending_filename)
                            log.debug(f"Associated TITLE '{pending_filename}' with link")
                            pending_filename = None  # Reset for next pair
                        else:
                            filenames.append(None)  # No TITLE= for this link
                    elif line:
                        log.debug(f"Ignoring non-link line: {line[:100]}...")

                log.info(f"Parsed {len(links)} links from {raw_url}.")
                # NEW: Store filenames in BOT.Options for access by parallel task code
                if any(filenames):  # Only set if at least one filename found
                    BOT.Options.filenames = filenames
                    log.info(f"Extracted {len([f for f in filenames if f])} TITLE= filenames")
                    # Debug: Log each filename
                    for i, fname in enumerate(filenames):
                        log.info(f"  [{i}] {fname}")
                else:
                    BOT.Options.filenames = []
                return links # Return only the list of links
    except Exception as e:
        log.error(f"Error fetching/parsing links from {raw_url}: {e}", exc_info=True)
        return None # Return None on error
# <<<  fetch_filenames FUNCTION >>>
async def fetch_filenames_from_url(url: str) -> list[str] | None:
    """
    Fetches content from supported raw text URLs (Pastebin, Gist, Rentry, .txt)
    and parses each NON-EMPTY line as a raw filename (strips whitespace only).
    Returns a list of raw filenames or None on failure or if URL is not supported.
    """
    log = logging.getLogger(__name__) # Ensure logger is defined
    log.debug(f"Attempting to fetch raw filenames from URL: {url}")
    raw_url = None
    cleaned_url = url.strip()
    is_recognized_source = False

    # --- Identify supported services and get raw URL ---
    if "pastebin.com" in cleaned_url:
        match = re.match(r"https?://pastebin\.com/raw/(\w+)", cleaned_url)
        if match: raw_url = cleaned_url; is_recognized_source = True
        else:
            match = re.match(r"https?://pastebin\.com/(\w+)", cleaned_url)
            if match: raw_url = f"https://pastebin.com/raw/{match.group(1)}"; is_recognized_source = True
    elif "gist.githubusercontent.com" in cleaned_url and "/raw" in cleaned_url:
         raw_url = cleaned_url; is_recognized_source = True
    elif "rentry.co" in cleaned_url:
        match = re.match(r"https?://rentry\.co/(\w+)", cleaned_url.split('/raw')[0]) # Get base code
        if match: raw_url = f"https://rentry.co/{match.group(1)}/raw"; is_recognized_source = True
    elif cleaned_url.lower().startswith(('http://', 'https://')) and cleaned_url.lower().endswith(".txt"):
         raw_url = cleaned_url; is_recognized_source = True
    # Add other raw text sites if needed

    if not raw_url:
        log.debug(f"URL not recognized as a supported raw filename source: {cleaned_url}")
        return None # Indicate not a supported URL type for fetching

    log.info(f"Attempting to fetch raw filenames from detected raw URL: {raw_url}")
    try:
        async with aiohttp.ClientSession() as session:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(raw_url, timeout=20, headers=headers) as response:
                log.debug(f"Fetching URL status: {response.status}")
                response.raise_for_status()
                text_content = await response.text()

                if not text_content:
                    log.warning(f"Fetched empty content from {raw_url}")
                    return [] # Return empty list if file is empty

                # --- NEW PARSING LOGIC ---
                # Parse raw filenames - one per line, just strip whitespace
                raw_filenames = []
                for line in text_content.splitlines():
                    stripped_line = line.strip()
                    if stripped_line: # Process non-empty lines after stripping
                        raw_filenames.append(stripped_line) # Add the raw, stripped line
                    # No cleaning or styling happens here anymore

                log.info(f"Found {len(raw_filenames)} non-empty lines (raw filenames) from {raw_url}")
                return raw_filenames # Returns the list of raw, stripped lines
                # --- END NEW PARSING LOGIC ---

    except aiohttp.ClientError as e:
        log.error(f"HTTP Client Error fetching raw filenames from {raw_url}: {e}")
        return None # Return None on fetch errors
    except Exception as e:
        log.error(f"Unexpected error fetching/parsing raw filenames from {raw_url}: {e}", exc_info=True)
        return None # Return None on other errors

# <<< END OF NEW FUNCTION >>>


def update_download_name_from_directory(directory_path: str, task_ctx: TaskContext = None) -> str:
    """Intelligently updates download_name based on files in the directory.

    This function inspects the downloaded files and creates a smart archive name:
    - Single file: uses that filename
    - Multiple files: extracts common prefix or uses smart naming

    Args:
        directory_path: Path to directory containing downloaded files
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        The determined name (without path, without extension for archives)
    """
    global Messages, log

    # Multi-task support
    if task_ctx:
        _messages = task_ctx.messages
    else:
        _messages = Messages

    if not ospath.exists(directory_path) or not ospath.isdir(directory_path):
        log.warning(f"update_download_name_from_directory: Invalid path: {directory_path}")
        return _messages.download_name or "Download"

    try:
        # Get all files in directory (excluding .aria2 temp files)
        all_items = os.listdir(directory_path)
        files = [f for f in all_items if ospath.isfile(ospath.join(directory_path, f)) and not f.endswith('.aria2')]

        if not files:
            log.warning(f"No files found in {directory_path}")
            return _messages.download_name or "Download"

        log.info(f"Found {len(files)} file(s) in {directory_path}: {files}")

        # Case 1: Single file - use its name (without extension for archive naming)
        if len(files) == 1:
            filename = files[0]
            name_without_ext, _ = ospath.splitext(filename)
            log.info(f"Single file detected, using name: {name_without_ext} (from {filename})")
            _messages.download_name = filename  # Store full filename
            return name_without_ext

        # Case 2: Multiple files - extract common prefix or use smart naming
        log.info(f"Multiple files detected ({len(files)}), applying smart naming...")

        # Strategy 1: Extract common prefix from all filenames
        common_prefix = _extract_common_prefix(files)
        if common_prefix and len(common_prefix) >= 3:  # Minimum 3 chars to be meaningful
            log.info(f"Using common prefix: {common_prefix}")
            _messages.download_name = common_prefix
            return common_prefix

        # Strategy 2: Use first file's name (strip numbers/extension)
        first_file = files[0]
        name_without_ext, _ = ospath.splitext(first_file)
        # Remove trailing numbers/episode indicators (e.g., "Movie1" -> "Movie", "S01E01" -> "S01")
        cleaned_name = re.sub(r'[-_\s]*\d+$', '', name_without_ext)
        if cleaned_name and len(cleaned_name) >= 3:
            log.info(f"Using cleaned first filename: {cleaned_name} (from {first_file})")
            _messages.download_name = cleaned_name
            return cleaned_name

        # Strategy 3: Use first file as-is
        log.info(f"Using first filename as-is: {name_without_ext}")
        _messages.download_name = first_file
        return name_without_ext

    except Exception as e:
        log.error(f"Error in update_download_name_from_directory: {e}", exc_info=True)
        return _messages.download_name or "Download"


def _extract_common_prefix(filenames: list) -> str:
    """Extract common prefix from a list of filenames.

    Args:
        filenames: List of filename strings

    Returns:
        Common prefix string, or empty string if no meaningful prefix found
    """
    if not filenames or len(filenames) < 2:
        return ""

    # Remove extensions for comparison
    names_no_ext = [ospath.splitext(f)[0] for f in filenames]

    # Find common prefix
    prefix = names_no_ext[0]
    for name in names_no_ext[1:]:
        # Find common characters from start
        common = ""
        for i, (c1, c2) in enumerate(zip(prefix, name)):
            if c1 == c2:
                common += c1
            else:
                break
        prefix = common
        if not prefix:  # No common prefix at all
            break

    # Clean up the prefix - remove trailing separators/numbers
    prefix = re.sub(r'[-_\s.]+$', '', prefix)  # Remove trailing separators
    prefix = re.sub(r'\d+$', '', prefix)  # Remove trailing numbers (e.g., "Movie1" -> "Movie")
    prefix = re.sub(r'[-_\s.]+$', '', prefix)  # Remove trailing separators again after number removal
    prefix = prefix.strip()

    return prefix
