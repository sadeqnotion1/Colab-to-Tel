#================================================
#FILE: colab_leecher/downlader/instagram.py
#================================================
import logging
import yt_dlp
import re
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import BOT, Messages, Paths, TRANSFER, TaskError
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO

log = logging.getLogger(__name__)


def is_profile_url(url: str) -> bool:
    """
    Check if URL is an Instagram profile URL.

    Returns:
        bool: True if profile URL, False if post/reel URL
    """
    # Profile patterns: instagram.com/username/ or instagram.com/username
    # NOT post patterns: instagram.com/p/xxx or instagram.com/reel/xxx
    profile_pattern = r'^https?://(?:www\.)?instagram\.com/([^/]+)/?$'

    if re.match(profile_pattern, url):
        # Make sure it's not a special page
        username = url.rstrip('/').split('/')[-1]
        special_pages = ['explore', 'p', 'reel', 'tv', 'stories', 'accounts', 'direct']
        return username not in special_pages

    return False


def extract_username(url: str) -> str:
    """Extract username from Instagram profile URL."""
    match = re.search(r'instagram\.com/([^/]+)', url)
    if match:
        return match.group(1)
    return ""


class InstagramState:
    """Holds state for Instagram download progress reporting."""
    header = ""
    speed = ""
    percentage = 0.0
    eta = ""
    done = ""
    left = ""
    current_file = ""


# Global state object shared across threads
_instagram_state = InstagramState()


async def instagram_download(link: str, num: int) -> bool:
    """
    Download from Instagram (posts, reels, stories, IGTV).

    Args:
        link: Instagram URL
        num: Link number for progress tracking

    Returns:
        bool: True if download successful, False otherwise
    """
    global Messages, Paths, TRANSFER, TaskError

    name = await get_instagram_title(link)
    Messages.download_name = name
    Messages.status_head = f"<b>📥 DOWNLOADING FROM INSTAGRAM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

    log.info(f"Starting Instagram download for link {num}: {link}")

    # Use instaloader instead of yt-dlp (more reliable for Instagram)
    instagram_thread = Thread(target=instagram_downloader_instaloader, name="InstagramDL", args=(link,))
    instagram_thread.start()

    # Use global state for progress tracking
    global _instagram_state

    while instagram_thread.is_alive():
        if _instagram_state.header:
            sys_text = sysINFO()
            message = _instagram_state.header
            try:
                from colab_leecher.utility.variables import MSG
                await MSG.status_msg.edit_text(
                    text=Messages.task_msg + Messages.status_head + message + sys_text,
                    reply_markup=keyboard()
                )
            except Exception:
                pass
        else:
            try:
                await status_bar(
                    down_msg=Messages.status_head,
                    speed=_instagram_state.speed,
                    percentage=float(_instagram_state.percentage),
                    eta=_instagram_state.eta,
                    done=_instagram_state.done,
                    left=_instagram_state.left,
                    engine="Instagram 📸",
                )
            except Exception:
                pass

        await sleep(2.5)

    # Check if download was successful
    success = check_instagram_success(name, link, num)
    return success


def instagram_downloader_instaloader(url):
    """
    Instagram single post downloader using instaloader.
    Runs in a separate thread to avoid blocking.
    """
    global _instagram_state

    try:
        import instaloader
        import json
        from pathlib import Path
        import re

        # Extract shortcode from URL
        match = re.search(r'/(?:p|reel|tv)/([^/?]+)', url)
        if not match:
            log.error(f"Could not extract shortcode from URL: {url}")
            TaskError.failed_links.append({
                "link": url,
                "filename": "instagram_post",
                "reason": "Invalid Instagram URL format"
            })
            return

        shortcode = match.group(1)

        # Create instaloader instance
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern='',
            filename_pattern='{profile}_{date_utc}_UTC',  # Include username in filename
            quiet=False
        )

        _instagram_state.header = f"⌛ __Setting up Instagram session...__"
        log.info("🔐 Loading Instagram session from cookies")

        # Load session from cookies (use JSON cookies file)
        if BOT.Setting.instagram_cookies_file:
            # Check for JSON cookies file
            json_cookie_path = BOT.Setting.instagram_cookies_file.replace('.txt', '.json')
            if ospath.exists(json_cookie_path):
                try:
                    with open(json_cookie_path, 'r') as f:
                        cookies_data = json.load(f)

                    # Extract sessionid from cookies
                    sessionid = None
                    for cookie in cookies_data:
                        if cookie.get('name') == 'sessionid':
                            sessionid = cookie.get('value')
                            break

                    if sessionid:
                        # Load session into instaloader
                        L.context._session.cookies.set('sessionid', sessionid, domain='.instagram.com')
                        log.info(f"✅ Loaded Instagram session")
                    else:
                        log.warning("No sessionid found in cookies")

                except Exception as cookie_err:
                    log.error(f"Failed to load Instagram cookies: {cookie_err}")
                    _instagram_state.header = f"⚠️ __Cookie loading failed, trying without auth...__"

        # Alternative: Use sessionid directly from settings
        elif BOT.Setting.instagram_sessionid:
            try:
                log.info("🔐 Loading Instagram session from INSTAGRAM_SESSIONID setting")
                L.context._session.cookies.set('sessionid', BOT.Setting.instagram_sessionid, domain='.instagram.com')
                log.info("✅ Loaded Instagram session")
            except Exception as session_err:
                log.error(f"Failed to load Instagram sessionid: {session_err}")
                _instagram_state.header = f"⚠️ __Session loading failed, trying without auth...__"

        # Create download directory
        makedirs(Paths.down_path, exist_ok=True)

        _instagram_state.header = f"📡 __Fetching post {shortcode}...__"
        log.info(f"📸 Downloading Instagram post: {shortcode}")

        # Get post from shortcode
        try:
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            log.info(f"✅ Found post by @{post.owner_username}")

            # Set better filename: username_shortcode (without domain and .bin)
            from ..utility.variables import Messages
            Messages.download_name = f"{post.owner_username}_{shortcode}"

            _instagram_state.header = f"📥 __Downloading post...__"

            # Download post
            L.dirname_pattern = Paths.down_path
            L.download_post(post, target=shortcode)

            log.info(f"✅ Downloaded post {shortcode}")
            _instagram_state.header = f"✅ __Download complete!__"

        except instaloader.exceptions.ProfileNotExistsException:
            log.error(f"Post {shortcode} does not exist")
            _instagram_state.header = f"❌ __Post not found__"
            TaskError.failed_links.append({
                "link": url,
                "filename": shortcode,
                "reason": "Post does not exist"
            })
        except instaloader.exceptions.LoginRequiredException:
            log.error(f"Login required to view post {shortcode} (private account)")
            _instagram_state.header = f"❌ __Private post - login required__"
            TaskError.failed_links.append({
                "link": url,
                "filename": shortcode,
                "reason": "Private post requires authentication"
            })
        except Exception as post_err:
            log.error(f"Failed to download post {shortcode}: {post_err}")
            _instagram_state.header = f"❌ __{str(post_err)[:50]}...__"
            TaskError.failed_links.append({
                "link": url,
                "filename": shortcode,
                "reason": f"Post download error: {str(post_err)[:100]}"
            })

    except ImportError:
        log.error("Instaloader not installed. Run: pip install instaloader")
        _instagram_state.header = f"❌ __Instaloader not installed__"
        TaskError.failed_links.append({
            "link": url,
            "filename": "instagram_post",
            "reason": "instaloader library not installed"
        })
    except Exception as e:
        log.error(f"❌ Unexpected error downloading post: {e}", exc_info=True)
        _instagram_state.header = f"❌ __Unexpected error: {str(e)[:50]}...__"
        TaskError.failed_links.append({
            "link": url,
            "filename": "instagram_post",
            "reason": f"Unexpected Error: {str(e)[:100]}"
        })


def instagram_downloader(url):
    """
    Instagram downloader using yt-dlp.
    Runs in a separate thread to avoid blocking.
    """
    instagram_state = InstagramState()

    def progress_hook(d):
        """Progress hook for yt-dlp to track download progress."""
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes", 0)
            dl_bytes = d.get("downloaded_bytes", 0)
            percent = d.get("downloaded_percent", 0)
            speed = d.get("speed", "N/A")
            eta = d.get("eta", 0)

            if total_bytes:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            instagram_state.header = ""
            instagram_state.speed = sizeUnit(speed) if speed else "N/A"
            instagram_state.percentage = percent
            instagram_state.eta = getTime(eta) if eta else "N/A"
            instagram_state.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
            instagram_state.left = sizeUnit(total_bytes) if total_bytes else "N/A"
            instagram_state.current_file = d.get("filename", "")

        elif d["status"] == "finished":
            log.info(f"Instagram download finished: {d.get('filename', 'unknown')}")

    # Instagram-specific yt-dlp options
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",  # Get best quality, merge video+audio if available
        "outtmpl": f"{Paths.down_path}/%(title)s.%(ext)s",  # Save with title as filename
        "writethumbnail": False,  # Don't save thumbnails separately
        "no_warnings": True,
        "ignoreerrors": True,  # Continue downloading other items if some fail (e.g., images in carousel)
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_color": True,
        # Instagram-specific options
        "extractor_args": {
            "instagram": {
                "include_ondemand_in_carousel": True,  # Include all carousel items
            }
        },
    }

    # Add Instagram authentication if credentials are provided (priority order)
    if BOT.Setting.instagram_cookies_file and ospath.exists(BOT.Setting.instagram_cookies_file):
        log.info(f"Using Instagram cookies from file: {BOT.Setting.instagram_cookies_file}")
        ydl_opts["cookiefile"] = BOT.Setting.instagram_cookies_file
    elif BOT.Setting.instagram_username and BOT.Setting.instagram_password:
        log.info(f"Using Instagram login: {BOT.Setting.instagram_username}")
        ydl_opts["username"] = BOT.Setting.instagram_username
        ydl_opts["password"] = BOT.Setting.instagram_password
    elif BOT.Setting.instagram_sessionid:
        log.info("Using Instagram session cookie for authentication")
        ydl_opts["cookiefile"] = None  # Disable cookie file
        # Set cookies directly via extractor_args
        ydl_opts["extractor_args"]["instagram"]["sessionid"] = BOT.Setting.instagram_sessionid
    else:
        log.info("Instagram authentication not configured - downloading without login")

    try:
        if not ospath.exists(Paths.down_path):
            makedirs(Paths.down_path)

        instagram_state.header = "⌛ __Extracting Instagram media information...__"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

            # Handle carousel/album (multiple images/videos)
            if "_type" in info_dict and info_dict["_type"] == "playlist":
                instagram_state.header = f"⏳ __Found {len(info_dict['entries'])} items in album...__"
                log.info(f"Instagram album detected with {len(info_dict['entries'])} items")

                # Create album directory
                album_name = info_dict.get("title", "instagram_album")
                album_path = ospath.join(Paths.down_path, album_name)
                if not ospath.exists(album_path):
                    makedirs(album_path)

                ydl_opts["outtmpl"] = f"{album_path}/%(title)s_%(autonumber)s.%(ext)s"

                with yt_dlp.YoutubeDL(ydl_opts) as ydl_album:
                    ydl_album.download([url])
            else:
                # Single post/reel/story
                instagram_state.header = ""
                Messages.download_name = info_dict.get("title", "instagram_media")
                ydl.download([url])

        log.info(f"Instagram download completed successfully for: {url}")

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        log.error(f"Instagram download error: {error_msg}")
        TaskError.failed_links.append({
            "link": url,
            "filename": Messages.download_name,
            "reason": f"DownloadError: {error_msg[:100]}"
        })
    except Exception as e:
        log.error(f"Unexpected Instagram download error: {e}", exc_info=True)
        TaskError.failed_links.append({
            "link": url,
            "filename": Messages.download_name,
            "reason": f"Unexpected Error: {str(e)[:100]}"
        })


async def get_instagram_title(link: str) -> str:
    """
    Extract the title/description from Instagram URL.

    Args:
        link: Instagram URL

    Returns:
        str: Title or username/post_id
    """
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=False)

            if "title" in info and info["title"]:
                return info["title"]
            elif "uploader" in info and info["uploader"]:
                return f"{info['uploader']}_instagram"
            else:
                # Extract from URL as fallback
                import re
                match = re.search(r'/(?:p|reel|tv)/([^/?]+)', link)
                if match:
                    return f"instagram_{match.group(1)}"
                return "instagram_media"
    except Exception as e:
        log.warning(f"Could not extract Instagram title: {e}")
        return "instagram_download"


def check_instagram_success(name: str, link: str, num: int) -> bool:
    """
    Check if Instagram download was successful by verifying file exists.

    Args:
        name: Expected filename
        link: Instagram URL
        num: Link number

    Returns:
        bool: True if successful, False otherwise
    """
    global Paths, TRANSFER, TaskError

    try:
        # Check if file exists in download directory (including subdirectories for albums)
        import os
        download_dir = Paths.down_path

        # Look for files matching the name pattern OR any media files (for instaloader)
        found_files = []

        # Check main directory
        for file in os.listdir(download_dir):
            file_path = os.path.join(download_dir, file)
            if os.path.isfile(file_path):
                # Match by name or any media file (jpg, mp4, png, etc)
                if (name in file or "instagram" in file.lower() or
                    file.lower().endswith(('.jpg', '.jpeg', '.png', '.mp4', '.mov'))):
                    found_files.append(file)
            # Check subdirectories (for album/carousel downloads)
            elif os.path.isdir(file_path) and (name in file or "instagram" in file.lower()):
                for subfile in os.listdir(file_path):
                    subfile_path = os.path.join(file_path, subfile)
                    if os.path.isfile(subfile_path):
                        found_files.append(os.path.join(file, subfile))

        if found_files:
            log.info(f"Instagram download successful. Found files: {found_files}")
            for file in found_files:
                TRANSFER.successful_downloads.append({
                    'url': link,
                    'filename': file
                })
            return True
        else:
            log.error(f"Instagram download failed. No files found for: {name}")
            TaskError.failed_links.append({
                "link": link,
                "filename": name,
                "index": num,
                "reason": "Output file not found"
            })
            return False

    except Exception as e:
        log.error(f"Error checking Instagram download success: {e}")
        TaskError.failed_links.append({
            "link": link,
            "filename": name,
            "index": num,
            "reason": f"Check failed: {str(e)[:100]}"
        })
        return False


async def instagram_profile_download(url: str, num: int, max_posts: int = 50) -> bool:
    """
    Download all posts from an Instagram profile using instaloader.

    Args:
        url: Instagram profile URL
        num: Link number for tracking
        max_posts: Maximum number of posts to download (default 50)

    Returns:
        bool: True if successful, False otherwise
    """
    global Messages, Paths, TRANSFER, TaskError, BOT

    username = extract_username(url)
    if not username:
        log.error(f"Could not extract username from URL: {url}")
        TaskError.failed_links.append({
            "link": url,
            "filename": "profile",
            "index": num,
            "reason": "Invalid profile URL"
        })
        return False

    Messages.download_name = f"{username}_profile"
    Messages.status_head = f"<b>📸 DOWNLOADING INSTAGRAM PROFILE » </b><i>@{username}</i>\n\n"

    log.info(f"Starting Instagram profile download: @{username} (max {max_posts} posts)")

    # Reset global state
    global _instagram_state
    _instagram_state.header = ""
    _instagram_state.speed = ""
    _instagram_state.percentage = 0.0
    _instagram_state.eta = ""
    _instagram_state.done = ""
    _instagram_state.left = ""
    _instagram_state.current_file = ""

    # Start download in a separate thread
    profile_thread = Thread(target=instagram_profile_downloader_instaloader, name="InstagramProfileDL", args=(url, username, max_posts))
    profile_thread.start()

    # Monitor progress
    while profile_thread.is_alive():
        if _instagram_state.header:
            sys_text = sysINFO()
            message = _instagram_state.header
            try:
                from colab_leecher.utility.variables import MSG
                await MSG.status_msg.edit_text(
                    text=Messages.task_msg + Messages.status_head + message + sys_text,
                    reply_markup=keyboard()
                )
            except Exception:
                pass
        else:
            try:
                await status_bar(
                    down_msg=Messages.status_head,
                    speed=_instagram_state.speed,
                    percentage=float(_instagram_state.percentage),
                    eta=_instagram_state.eta,
                    done=_instagram_state.done,
                    left=_instagram_state.left,
                    engine="Instagram 📸",
                )
            except Exception:
                pass

        await sleep(2.5)

    # Check if download was successful
    success = check_profile_download_success(username, url, num)
    return success


def instagram_profile_downloader(url: str, username: str, max_posts: int):
    """
    Instagram profile downloader using yt-dlp.
    Runs in a separate thread to avoid blocking.
    """
    instagram_state = InstagramState()

    def progress_hook(d):
        """Progress hook for yt-dlp to track download progress."""
        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes", 0)
            dl_bytes = d.get("downloaded_bytes", 0)
            percent = d.get("downloaded_percent", 0)
            speed = d.get("speed", "N/A")
            eta = d.get("eta", 0)

            if total_bytes:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            instagram_state.header = ""
            instagram_state.speed = sizeUnit(speed) if speed else "N/A"
            instagram_state.percentage = percent
            instagram_state.eta = getTime(eta) if eta else "N/A"
            instagram_state.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
            instagram_state.left = sizeUnit(total_bytes) if total_bytes else "N/A"
            instagram_state.current_file = d.get("filename", "")

        elif d["status"] == "finished":
            filename = d.get("filename", "unknown")
            log.info(f"Instagram profile download finished: {filename}")

    # Create profile directory
    profile_dir = ospath.join(Paths.down_path, f"{username}_profile")
    makedirs(profile_dir, exist_ok=True)

    # Instagram profile-specific yt-dlp options
    ydl_opts = {
        "format": "best",
        "outtmpl": f"{profile_dir}/%(title)s_%(id)s.%(ext)s",
        "writethumbnail": False,
        "no_warnings": False,
        "ignoreerrors": True,  # Continue on errors
        "progress_hooks": [progress_hook],
        "quiet": False,
        "no_color": True,
        # Limit number of posts
        "playlistend": max_posts,
        # Instagram-specific options
        "extractor_args": {
            "instagram": {
                "include_ondemand_in_carousel": True,
            }
        },
    }

    # Add Instagram authentication with cookies (required for profiles)
    if BOT.Setting.instagram_cookies_file and ospath.exists(BOT.Setting.instagram_cookies_file):
        log.info(f"🍪 Using Instagram cookies from file: {BOT.Setting.instagram_cookies_file}")

        # Convert JSON cookies to Netscape format for yt-dlp
        import json
        import tempfile
        from pathlib import Path

        try:
            cookie_path = Path(BOT.Setting.instagram_cookies_file)
            with open(cookie_path, 'r') as f:
                cookies_data = json.load(f)

            # Create temporary Netscape cookies file
            netscape_cookies = "# Netscape HTTP Cookie File\n"
            for cookie in cookies_data:
                domain = cookie.get('domain', '.instagram.com')
                flag = "TRUE" if domain.startswith('.') else "FALSE"
                path = cookie.get('path', '/')
                secure = "TRUE" if cookie.get('secure', True) else "FALSE"
                expiration = str(cookie.get('expirationDate', 0)).split('.')[0]
                name = cookie.get('name', '')
                value = cookie.get('value', '')

                if name and value:
                    netscape_cookies += f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n"

            # Write to temporary file
            temp_cookie_file = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt')
            temp_cookie_file.write(netscape_cookies)
            temp_cookie_file.close()

            ydl_opts["cookiefile"] = temp_cookie_file.name
            log.info(f"✅ Converted {len(cookies_data)} cookies to Netscape format")

        except Exception as cookie_err:
            log.error(f"Failed to load cookies: {cookie_err}")
            instagram_state.header = f"⚠️ Cookie loading failed, trying without auth..."

    elif BOT.Setting.instagram_username and BOT.Setting.instagram_password:
        log.info(f"Using Instagram login: {BOT.Setting.instagram_username}")
        ydl_opts["username"] = BOT.Setting.instagram_username
        ydl_opts["password"] = BOT.Setting.instagram_password
    else:
        log.warning("⚠️ No Instagram authentication configured - this may fail for profiles")

    try:
        instagram_state.header = f"⌛ __Extracting profile information for @{username}...__"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            log.info(f"📡 Fetching profile: {url}")
            info_dict = ydl.extract_info(url, download=False)

            # Check if extraction succeeded
            if info_dict is None:
                log.error(f"❌ yt-dlp failed to extract profile info for @{username}")
                instagram_state.header = f"❌ __Instagram profile extraction failed__"
                TaskError.failed_links.append({
                    "link": url,
                    "filename": username,
                    "reason": "yt-dlp Instagram extractor is currently broken. Instagram frequently breaks scraping tools."
                })
                return

            # Profile downloads return playlist type
            if "_type" in info_dict and info_dict["_type"] == "playlist":
                total_posts = len(info_dict.get("entries", []))
                instagram_state.header = f"✅ __Found {total_posts} posts from @{username}__\n⬇️ __Downloading...__"
                log.info(f"📸 Found {total_posts} posts from @{username}")
            else:
                instagram_state.header = f"⚠️ __Profile format unexpected, attempting download...__"
                log.warning("Profile info format unexpected")

            # Download all posts
            instagram_state.header = ""
            log.info(f"⬇️ Starting batch download to: {profile_dir}")
            ydl.download([url])

        log.info(f"✅ Instagram profile download completed for @{username}")

        # Clean up temp cookie file if created
        if "cookiefile" in ydl_opts and ydl_opts["cookiefile"]:
            try:
                import os
                os.unlink(ydl_opts["cookiefile"])
            except:
                pass

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        log.error(f"❌ Instagram profile download error: {error_msg}")

        # Check if it's an authentication error
        if "login" in error_msg.lower() or "private" in error_msg.lower():
            instagram_state.header = f"❌ __Authentication required or private account__"
            TaskError.failed_links.append({
                "link": url,
                "filename": username,
                "reason": "Authentication required - Please provide Instagram cookies"
            })
        else:
            instagram_state.header = f"❌ __{error_msg[:50]}...__"
            TaskError.failed_links.append({
                "link": url,
                "filename": username,
                "reason": f"DownloadError: {error_msg[:100]}"
            })
    except Exception as e:
        log.error(f"❌ Unexpected error downloading profile @{username}: {e}", exc_info=True)
        instagram_state.header = f"❌ __Unexpected error: {str(e)[:50]}...__"
        TaskError.failed_links.append({
            "link": url,
            "filename": username,
            "reason": f"Unexpected Error: {str(e)[:100]}"
        })


def check_profile_download_success(username: str, link: str, num: int) -> bool:
    """
    Check if Instagram profile download was successful.

    Args:
        username: Instagram username
        link: Profile URL
        num: Link number

    Returns:
        bool: True if successful, False otherwise
    """
    global Paths, TRANSFER, TaskError

    try:
        import os
        profile_dir = ospath.join(Paths.down_path, f"{username}_profile")

        if not ospath.exists(profile_dir):
            log.error(f"Profile directory not found: {profile_dir}")
            TaskError.failed_links.append({
                "link": link,
                "filename": username,
                "index": num,
                "reason": "Profile directory not created"
            })
            return False

        # Count downloaded files
        downloaded_files = [f for f in os.listdir(profile_dir) if ospath.isfile(ospath.join(profile_dir, f))]

        if not downloaded_files:
            log.error(f"No files downloaded for @{username}")
            TaskError.failed_links.append({
                "link": link,
                "filename": username,
                "index": num,
                "reason": "No files downloaded (may be private or require auth)"
            })
            return False

        log.info(f"✅ Instagram profile download successful: {len(downloaded_files)} files from @{username}")

        # Track all successful downloads
        for filename in downloaded_files:
            TRANSFER.successful_downloads.append({
                'url': link,
                'filename': filename
            })

        return True

    except Exception as e:
        log.error(f"Error checking profile download success: {e}")
        TaskError.failed_links.append({
            "link": link,
            "filename": username,
            "index": num,
            "reason": f"Check failed: {str(e)[:100]}"
        })
        return False


def instagram_profile_downloader_instaloader(url: str, username: str, max_posts: int):
    """
    Instagram profile downloader using instaloader.
    Runs in a separate thread to avoid blocking.
    """
    global _instagram_state

    try:
        import instaloader
        import json
        from pathlib import Path

        # Create instaloader instance
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_geotags=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern='',
            filename_pattern='{profile}_{date_utc}_UTC',  # Include username in filename
            quiet=False
        )

        _instagram_state.header = f"⌛ __Setting up Instagram session...__"
        log.info("🔐 Loading Instagram session from cookies")

        # Load session from cookies
        if BOT.Setting.instagram_cookies_file and ospath.exists(BOT.Setting.instagram_cookies_file):
            try:
                cookie_path = Path(BOT.Setting.instagram_cookies_file)
                with open(cookie_path, 'r') as f:
                    cookies_data = json.load(f)

                # Extract sessionid from cookies
                sessionid = None
                for cookie in cookies_data:
                    if cookie.get('name') == 'sessionid':
                        sessionid = cookie.get('value')
                        break

                if sessionid:
                    # Get username from sessionid (format: userid%3A...)
                    user_id = BOT.Setting.instagram_sessionid.split('%3A')[0] if BOT.Setting.instagram_sessionid else None

                    # Try to load existing session or create new one
                    session_file = Path("instagram_session")

                    # Instaloader uses session files - try to import session
                    try:
                        # Login with sessionid
                        L.context._session.cookies.set('sessionid', sessionid, domain='.instagram.com')
                        L.context.username = user_id or "unknown"
                        log.info(f"✅ Loaded Instagram session for user")
                    except Exception as session_err:
                        log.warning(f"Could not load session: {session_err}")
                else:
                    log.warning("No sessionid found in cookies")

            except Exception as cookie_err:
                log.error(f"Failed to load Instagram cookies: {cookie_err}")
                _instagram_state.header = f"⚠️ __Cookie loading failed, trying without auth...__"

        # Create profile directory
        profile_dir = ospath.join(Paths.down_path, f"{username}_profile")
        makedirs(profile_dir, exist_ok=True)
        L.dirname_pattern = profile_dir

        _instagram_state.header = f"📡 __Fetching profile @{username}...__"
        log.info(f"📸 Downloading profile: @{username}")

        # Get profile
        try:
            profile = instaloader.Profile.from_username(L.context, username)
            log.info(f"✅ Found profile @{username} - {profile.mediacount} total posts")

            # Show limit only if it's actually limiting (less than total posts)
            limit_text = f" (limit: {max_posts})" if max_posts < profile.mediacount else ""
            _instagram_state.header = f"✅ __Found {profile.mediacount} posts__\n⬇️ __Downloading all{limit_text}...__"

            # Download posts
            downloaded_count = 0
            for idx, post in enumerate(profile.get_posts(), 1):
                if idx > max_posts:
                    log.info(f"Reached max_posts limit ({max_posts})")
                    break

                try:
                    _instagram_state.header = f"📥 __Downloading post {idx}/{min(max_posts, profile.mediacount)}...__"

                    # Download post
                    L.download_post(post, target=username)
                    downloaded_count += 1

                    log.info(f"✅ Downloaded post {idx}/{max_posts}")

                except instaloader.exceptions.LoginRequiredException:
                    log.error(f"Login required for post {idx}")
                    _instagram_state.header = f"❌ __Login required (private account)__"
                    TaskError.failed_links.append({
                        "link": url,
                        "filename": username,
                        "reason": "Login required - account may be private"
                    })
                    break
                except Exception as post_err:
                    log.warning(f"Failed to download post {idx}: {post_err}")
                    continue

            log.info(f"✅ Profile download complete: {downloaded_count} posts from @{username}")
            _instagram_state.header = f"✅ __Downloaded {downloaded_count} posts!__"

        except instaloader.exceptions.ProfileNotExistsException:
            log.error(f"Profile @{username} does not exist")
            _instagram_state.header = f"❌ __Profile not found__"
            TaskError.failed_links.append({
                "link": url,
                "filename": username,
                "reason": "Profile does not exist"
            })
        except instaloader.exceptions.LoginRequiredException:
            log.error(f"Login required to view @{username} (private account)")
            _instagram_state.header = f"❌ __Private account - login required__"
            TaskError.failed_links.append({
                "link": url,
                "filename": username,
                "reason": "Private account requires authentication"
            })
        except Exception as profile_err:
            log.error(f"Failed to fetch profile @{username}: {profile_err}")
            _instagram_state.header = f"❌ __{str(profile_err)[:50]}...__"
            TaskError.failed_links.append({
                "link": url,
                "filename": username,
                "reason": f"Profile fetch error: {str(profile_err)[:100]}"
            })

    except ImportError:
        log.error("Instaloader not installed. Run: pip install instaloader")
        _instagram_state.header = f"❌ __Instaloader not installed__"
        TaskError.failed_links.append({
            "link": url,
            "filename": username,
            "reason": "instaloader library not installed"
        })
    except Exception as e:
        log.error(f"❌ Unexpected error downloading profile @{username}: {e}", exc_info=True)
        _instagram_state.header = f"❌ __Unexpected error: {str(e)[:50]}...__"
        TaskError.failed_links.append({
            "link": url,
            "filename": username,
            "reason": f"Unexpected Error: {str(e)[:100]}"
        })
