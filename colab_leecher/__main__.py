# /content/Telegram-Leecher/colab_leecher/__main__.py

from . import aliases  # registers /mirror,/leech,/ytdl,/count,/del,/stats
import logging, os
import asyncio
import re # Import regex module
import aiohttp # Import aiohttp
import random # Import random for thumbnail selection
import aiofiles # Import aiofiles for async file writing
from pyrogram import filters, Client, ContinuePropagation
from datetime import datetime
from asyncio import sleep, get_event_loop
from colab_leecher import colab_bot, OWNER, DUMP_ID # Absolute import
from .utility.handler import cancelTask
from .utility.variables import BOT, MSG, BotTimes, Paths, TRANSFER, TaskError, Aria2c
from .utility.task_context import TaskContext, TASK_QUEUE, create_task_context
from .utility.task_dashboard import update_summary_dashboard, force_update_summary
from .utility.task_manager import taskScheduler, task_starter
from .utility.helper import (
    isLink, setThumbnail, message_deleter, send_settings,
    clean_filename, extract_filename_from_url, apply_dot_style, sizeUnit # Import sizeUnit if needed
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
# Example import line in __main__.py
from .utility.helper import (
    isLink, setThumbnail, message_deleter, send_settings,
    clean_filename, extract_filename_from_url, apply_dot_style, sizeUnit,
    keyboard, fetch_links_from_url, fetch_filenames_from_url
)
from .downlader.mindvalley import MindvalleyDownloader
from .uploader.telegram import upload_file
from .utility.handler import SendLogs


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

log.info(f"--> MERGED V1: colab_bot instance used in __main__.py: ID = {id(colab_bot)}")

src_request_msg = None
reply_prompt_message_id = None
extract_request_msg = None  # Track when waiting for extract path input

# --- Helper function to ask for leech type (normal/zip/unzip) ---
async def ask_leech_type(client, chat_id, mode_name, reply_to_message_id=None):
    log.info(f"Asking leech type (Mode: {mode_name}) for chat {chat_id}")
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Regular", callback_data="leechtype_normal")],
         [InlineKeyboardButton("Compress", callback_data="leechtype_zip"), InlineKeyboardButton("Extract", callback_data="leechtype_unzip")],
         [InlineKeyboardButton("UnDoubleZip", callback_data="leechtype_undzip")],
         [InlineKeyboardButton("Cancel Task", callback_data="cancel")]] # Add cancel here
    )
    text = f"<b> Select Processing Type You Want » </b>\n\nRegular:<i> Normal file upload</i>\nCompress:<i> Zip file upload</i>\nExtract:<i> extract before upload</i>\nUnDoubleZip:<i> Unzip then compress</i>"
    try:
        # Send as new message instead of editing/replying maybe?
        await client.send_message(chat_id, text, reply_markup=keyboard)
        # if reply_to_message_id: await client.send_message(chat_id, text, reply_markup=keyboard, reply_to_message_id=reply_to_message_id)
        # else: await client.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as e: log.error(f"Failed send leech type prompt: {e}", exc_info=True)

# --- Helper function to ask for filename option (Debrid/bitso) ---
async def ask_filename_option(client, chat_id, service_name):
    log.info(f"Asking filename option for {service_name}")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Yes, Extract from URL", callback_data=f'fn_{service_name.lower()}_extract')],
        [InlineKeyboardButton("No, Provide Manually", callback_data=f'fn_{service_name.lower()}_manual')],
        [InlineKeyboardButton("Cancel Task", callback_data='cancel')]
    ])
    await client.send_message(chat_id, f"🏷️ For {service_name}, extract filenames automatically from URLs?", reply_markup=keyboard)

# --- Helper function to ask for manual filenames ---
async def ask_manual_filenames(client, chat_id, service_name, count):
    global reply_prompt_message_id
    log.info(f"Asking for {count} manual filenames for {service_name}")
    prompt_msg = await client.send_message(chat_id, f"📝 Okay, **reply to this message** with the {count} filename(s) for {service_name}, one per line.")
    reply_prompt_message_id = prompt_msg.id # Store prompt ID

# --- Existing Command Handlers ---
@colab_bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    log.info(f"Received /start from {message.from_user.id}")
    await message.delete(); text = "**Yo! 👋🏼 It's Colab Leecher** ..."; keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Repo", url="https://github.com/thesadeq/Telegram-Leecher")]]); await message.reply_text(text, reply_markup=keyboard)

@colab_bot.on_message(filters.command("tupload") & filters.private)
async def telegram_upload(client, message):
    global BOT, src_request_msg
    log.info(f"Received /tupload from {message.from_user.id}")
    BOT.Mode.mode = "leech"; BOT.Mode.ytdl = False; BOT.Options.service_type = None # Reset service type
    text = "<b>⚡ Leech Task » Send Me THEM LINK(s) 🔗</b>\n\n(Direct, Magnet, TG, Mega, GDrive, Debrid, NZB, bitso, Downloadly)\n\n<code>https//link1.xyz\n[name.ext]\n{zip_pw}\n(unzip_pw)</code>"
    src_request_msg = await task_starter(message, text)
    log.debug(f"/tupload: task_starter called, src_request_msg set")


@colab_bot.on_message(filters.command("gdupload") & filters.private)
async def drive_upload(client, message):
    global BOT, src_request_msg
    log.info(f"Received /gdupload from {message.from_user.id}")
    BOT.Mode.mode = "mirror"; BOT.Mode.ytdl = False; BOT.Options.service_type = None # Reset service type
    text = "<b>♻️ Mirror Task » Send Me THEM LINK(s) 🔗</b>\n\n(Direct, Magnet, TG, Mega, GDrive, Debrid, NZB, bitso, Downloadly)\n\n<code>https//link1.xyz\n[name.ext]\n{zip_pw}\n(unzip_pw)</code>"
    src_request_msg = await task_starter(message, text)
    log.debug(f"/gdupload: task_starter called, src_request_msg set")

@colab_bot.on_message(filters.command("drupload") & filters.private)
async def directory_upload(client, message):
    global BOT, src_request_msg
    log.info(f"Received /drupload from {message.from_user.id}")
    BOT.Mode.mode = "dir-leech"; BOT.Mode.ytdl = False; BOT.Options.service_type = "local" # Set service type
    text = "<b>⚡ Dir Leech » Send Me FOLDER PATH 🔗</b> ...<code>/path/to/folder</code>"
    src_request_msg = await task_starter(message, text)
    log.debug(f"/drupload: task_starter called, src_request_msg set")

@colab_bot.on_message(filters.command("ytupload") & filters.private)
async def yt_upload(client, message):
    global BOT, src_request_msg
    log.info(f"Received /ytupload from {message.from_user.id}")
    BOT.Mode.mode = "leech"; BOT.Mode.ytdl = True; BOT.Options.service_type = "ytdl" # Set service type
    text = "<b>🏮 YTDL Leech » Send Me LINK(s) 🔗</b> ...<code>https//link1.mp4</code>"
    src_request_msg = await task_starter(message, text)
    log.debug(f"/ytupload: task_starter called, src_request_msg set")

# --- REMOVED /nzbclouddownload, /Debriddownload, /bitsodownload handlers ---

@colab_bot.on_message(filters.command("settings") & filters.private)
async def settings(client, message):
    log.info(f"Received /settings from {message.from_user.id}")
    if message.chat.id == OWNER: await message.delete(); await send_settings(client, message, message.id, True)
    else: log.warning(f"Unauthorized /settings from {message.from_user.id}")

# --- Reply Handler: Simplified for filenames only ---
@colab_bot.on_message(filters.reply & filters.private)
async def handle_reply(client: Client, message: Message):
    global BOT, reply_prompt_message_id, src_request_msg # Declare globals used
    log = logging.getLogger(__name__) # Ensure logger access
    log.debug(f"Received reply (ID: {message.id}) from user {message.from_user.id}")

    # Check if the reply is for the expected prompt message ID
    if not reply_prompt_message_id or not message.reply_to_message_id or message.reply_to_message_id != reply_prompt_message_id:
        log.debug(f"Reply (ID: {message.id}) is not for the expected prompt message ID ({reply_prompt_message_id}). Ignoring.")
        return

    # Try to get the original prompt message (optional, for deletion/context)
    original_prompt_msg = None
    try:
        if message.reply_to_message_id:
            original_prompt_msg = await client.get_messages(message.chat.id, message.reply_to_message_id)
    except Exception as get_err:
        log.warning(f"Could not get original prompt message {message.reply_to_message_id}: {get_err}")

    state_handled = False
    mode_name = "" # Initialize mode_name
    current_service = BOT.Options.service_type # Get selected service

    try:
        # --- Handle Filename Replies ---
        # Check if we are expecting filenames for any supported service
        expecting_filenames_now = (current_service == "nzbcloud" and BOT.State.expecting_nzb_filenames) or \
                                  (current_service == "Debrid" and BOT.State.expecting_Debrid_filenames) or \
                                  (current_service == "bitso" and BOT.State.expecting_bitso_filenames)

        if expecting_filenames_now:
            log.info(f"Processing filename reply for service: {current_service}...")
            user_input = message.text.strip() if message.text else "" # Ensure text exists
            expected_count = len(BOT.SOURCE) # Determine expected count *once*

            # <<< --- START LOGGING (Expected Count) --- >>>
            log.debug(f"HANDLE_REPLY: Expecting {expected_count} filenames based on BOT.SOURCE.")
            log.debug(f"HANDLE_REPLY: BOT.SOURCE content (first 5): {BOT.SOURCE[:5] if BOT.SOURCE else '[]'}")
            # <<< --- END LOGGING --- >>>

            filenames_to_use = []
            input_processed = False

            # Check if the input looks like a supported URL for filenames
            is_potential_url = False
            if user_input.lower().startswith(('http://', 'https://')):
                # Basic check, fetch_filenames_from_url will do a more specific check
                if ("pastebin.com" in user_input or "gist.githubusercontent.com" in user_input or
                    "rentry.co" in user_input or user_input.lower().endswith(".txt")):
                      is_potential_url = True

            # --- Process URL Input ---
            if is_potential_url:
                log.info(f"Detected potential filename URL: {user_input}")
                # fetch_filenames_from_url now returns raw, stripped lines
                raw_lines_list = await fetch_filenames_from_url(user_input)

                # Get counts for comparison
                fetched_count = len(raw_lines_list) if raw_lines_list is not None else -1

                # <<< --- START LOGGING (URL) --- >>>
                log.debug(f"HANDLE_REPLY (URL): Raw lines fetched from URL: {raw_lines_list}")
                log.debug(f"HANDLE_REPLY (URL): Comparing Counts -> Fetched: {fetched_count}, Expected: {expected_count}")
                # <<< --- END LOGGING --- >>>

                if raw_lines_list is None:
                    # Fetching failed
                    await message.reply_text(f"❌ Failed to fetch filenames from the provided URL or it's unsupported. Please provide a direct reply or a valid raw link (Gist/Pastebin/Rentry/.txt).", quote=True)
                    log.warning(f"fetch_filenames_from_url returned None for: {user_input}")
                    # Keep expecting reply (don't set state_handled=True)

                elif fetched_count != expected_count:
                    # Count mismatch based on raw lines
                    log.warning("Raw filename line count mismatch.")
                    await message.reply_text(f"❌ Found {fetched_count} non-empty lines in the URL, but expected {expected_count} filenames (matching the number of links). Please check the file content and reply again.", quote=True)
                    # Keep expecting reply (don't set state_handled=True)

                else:
                    # Counts match! Now clean and style the raw lines
                    log.info(f"Raw line count matches expected count ({expected_count}). Cleaning/styling filenames...")
                    filenames_to_use = []
                    all_valid_after_cleaning = True
                    for i, raw_line in enumerate(raw_lines_list):
                        cleaned = clean_filename(raw_line)
                        if cleaned:
                            styled = apply_dot_style(cleaned)
                            filenames_to_use.append(styled)
                        else:
                            log.warning(f"Filename at line {i+1} ('{raw_line[:50]}...') became invalid after cleaning. Aborting.")
                            await message.reply_text(f"❌ Filename at line {i+1} ('{raw_line[:50]}...') is invalid after cleaning. Please check your list and reply again.", quote=True)
                            all_valid_after_cleaning = False
                            break # Stop processing if any filename is invalid

                    if all_valid_after_cleaning:
                        # Success! All filenames cleaned successfully
                        BOT.Options.filenames = filenames_to_use # Store the final cleaned list
                        input_processed = True
                        log.info(f"Successfully cleaned and stored {len(filenames_to_use)} filenames from URL.")
                    # Else (all_valid_after_cleaning is False): Error message already sent, loop broken.

            # --- Process Direct Text Input ---
            else:
                log.info("Processing input as direct filename list.")
                filenames_raw = [fn.strip() for fn in user_input.splitlines() if fn.strip()]
                fetched_count = len(filenames_raw) # Get count of non-empty raw lines

                # <<< --- START LOGGING (Direct) --- >>>
                log.debug(f"HANDLE_REPLY (Direct): Raw lines from input: {filenames_raw}")
                log.debug(f"HANDLE_REPLY (Direct): Comparing Counts -> Fetched: {fetched_count}, Expected: {expected_count}")
                # <<< --- END LOGGING --- >>>

                if fetched_count != expected_count:
                     # Count mismatch based on direct input lines
                     log.warning("Filename count mismatch (direct input).")
                     await message.reply_text(f"❌ Expected {expected_count} filenames, but got {fetched_count}. Reply again with the correct number of filenames.", quote=True)
                     # Keep expecting reply (don't set state_handled=True)
                else:
                     # Counts match! Now clean and style the raw lines
                     log.info(f"Direct input count matches expected count ({expected_count}). Cleaning/styling filenames...")
                     filenames_to_use = []
                     all_valid_after_cleaning = True
                     for i, raw_line in enumerate(filenames_raw):
                         cleaned = clean_filename(raw_line)
                         if cleaned:
                             styled = apply_dot_style(cleaned)
                             filenames_to_use.append(styled)
                         else:
                             log.warning(f"Direct filename at line {i+1} ('{raw_line[:50]}...') became invalid after cleaning. Aborting.")
                             await message.reply_text(f"❌ Filename at line {i+1} ('{raw_line[:50]}...') is invalid after cleaning. Please check your input and reply again.", quote=True)
                             all_valid_after_cleaning = False
                             break # Stop processing if any filename is invalid

                     if all_valid_after_cleaning:
                          # Success! All filenames cleaned successfully
                          BOT.Options.filenames = filenames_to_use # Store the final cleaned list
                          input_processed = True
                          log.info(f"Successfully cleaned and stored {len(filenames_to_use)} filenames from direct input.")

            # --- Post-processing (only if input_processed is True) ---
            if input_processed:
                state_handled = True
                # Reset specific state and get mode name
                if current_service == "nzbcloud": BOT.State.expecting_nzb_filenames = False; mode_name = "NZBCloud"
                elif current_service == "Debrid": BOT.State.expecting_Debrid_filenames = False; mode_name = "DebridLeech"
                elif current_service == "bitso": BOT.State.expecting_bitso_filenames = False; mode_name = "bitso"
                log.info(f"Received valid filenames for {mode_name} ({'URL' if is_potential_url else 'Direct'}).")

                # Try deleting the original prompt message if obtained
                if original_prompt_msg:
                    try: await original_prompt_msg.delete()
                    except Exception as del_err: log.warning(f"Could not delete original prompt: {del_err}")

                # Filenames received, now ask for leech type (normal/zip/unzip)
                # Make sure ask_leech_type is correctly imported/defined
                await ask_leech_type(client, message.chat.id, BOT.Mode.mode)


        # --- Handle Prefix/Suffix replies ---
        elif BOT.State.prefix:
            log.info("Processing prefix reply...")
            BOT.Setting.prefix = message.text.strip() if message.text else "" # Strip whitespace
            BOT.State.prefix = False
            state_handled = True
            # Try sending updated settings if original prompt message exists
            if original_prompt_msg:
                try:
                    # Make sure send_settings is correctly imported/defined
                    await send_settings(client, original_prompt_msg, original_prompt_msg.id, False)
                except Exception as send_err:
                    log.error(f"Failed to send settings after prefix: {send_err}")
                    await message.reply_text("Prefix set!") # Fallback confirmation
            else:
                await message.reply_text("Prefix set!") # Fallback confirmation


        elif BOT.State.suffix:
            log.info("Processing suffix reply...")
            BOT.Setting.suffix = message.text.strip() if message.text else "" # Strip whitespace
            BOT.State.suffix = False
            state_handled = True
            # Try sending updated settings if original prompt message exists
            if original_prompt_msg:
                try:
                    # Make sure send_settings is correctly imported/defined
                    await send_settings(client, original_prompt_msg, original_prompt_msg.id, False)
                except Exception as send_err:
                    log.error(f"Failed to send settings after suffix: {send_err}")
                    await message.reply_text("Suffix set!") # Fallback confirmation
            else:
                await message.reply_text("Suffix set!") # Fallback confirmation

        else:
            # This case should ideally not be reached if the prompt ID check works
            log.warning(f"Received reply (for msg {reply_prompt_message_id}) but no matching state active. Ignoring.")

    except Exception as e:
        log.error(f"Error processing reply: {e}", exc_info=True)
        # Inform user about the error
        try: await message.reply_text(f"⚠️ Error processing your reply: {e}", quote=True)
        except Exception: pass # Ignore if sending error fails

    finally:
        # --- Final cleanup inside handle_reply ---
        if state_handled:
            log.debug(f"State handled for reply {message.id}. Resetting prompt ID.")
            reply_prompt_message_id = None # Reset prompt ID as it's been handled
            try:
                # Check if message exists before deleting
                if message: await message.delete() # Delete user's reply
            except Exception as del_err:
                 log.warning(f"Could not delete user reply message {message.id if message else 'N/A'}: {del_err}")
        else:
            # Only log if we were actually expecting a reply (prompt ID was set)
            if reply_prompt_message_id == message.reply_to_message_id:
                 log.debug(f"State not handled for reply {message.id}. Prompt ID {reply_prompt_message_id} remains active.")
            # No need to log if the reply wasn't for our prompt anyway


async def fetch_and_parse_links(url: str) -> list[str] | None:
    """
    Fetches content from supported raw text URLs (Pastebin, Gist, Rentry)
    and parses valid links (http/https/magnet).
    Returns a list of links or None on failure or if URL is not supported.
    """
    log = logging.getLogger(__name__) # Get logger instance
    # Ensure necessary modules are imported where this function is defined
    import re
    import aiohttp

    raw_url = None
    cleaned_url = url.strip() # Clean input URL

    # --- Identify supported services and get raw URL ---
    if "pastebin.com" in cleaned_url:
        match = re.match(r"https?://pastebin\.com/raw/(\w+)", cleaned_url)
        if match:
            raw_url = cleaned_url
        else:
            match = re.match(r"https?://pastebin\.com/(\w+)", cleaned_url)
            if match:
                raw_url = f"https://pastebin.com/raw/{match.group(1)}"
    elif "gist.githubusercontent.com" in cleaned_url and "/raw" in cleaned_url:
         # Directly handle raw gist URLs
         raw_url = cleaned_url
    elif "rentry.co" in cleaned_url:
        match = re.match(r"https?://rentry\.co/(\w+)", cleaned_url.split('/raw')[0]) # Get base code
        if match:
            raw_url = f"https://rentry.co/{match.group(1)}/raw" # Ensure /raw

    # Add simple check for direct .txt links
    elif cleaned_url.lower().startswith(('http://', 'https://')) and cleaned_url.lower().endswith(".txt"):
         raw_url = cleaned_url

    if not raw_url:
        # log.debug(f"URL not recognized as a supported raw paste/gist/rentry/txt link: {cleaned_url}")
        return None # Indicate not a supported URL type for fetching

    log.info(f"Attempting to fetch links from detected raw URL: {raw_url}")
    try:
        async with aiohttp.ClientSession() as session:
            # Add headers to potentially mimic a browser
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(raw_url, timeout=20, headers=headers) as response: # Increased timeout
                log.debug(f"Fetching URL status: {response.status}")
                response.raise_for_status() # Raise exception for bad status codes
                text_content = await response.text()

                if not text_content:
                    log.warning(f"Fetched empty content from {raw_url}")
                    return []

                # Parse links - one per line, basic validation
                links = []
                for line in text_content.splitlines():
                    line = line.strip()
                    # Basic check for http/https/magnet/ftp links - refine regex if needed
                    if re.match(r"^(https?://|magnet:\?|ftps?://)", line):
                        links.append(line)
                    elif line: # Log non-empty lines that don't look like links
                         log.debug(f"Ignoring non-link line: {line[:100]}...")


                log.info(f"Parsed {len(links)} links from {raw_url}")
                return links

    except aiohttp.ClientError as e:
        log.error(f"HTTP Client Error fetching links from {raw_url}: {e}")
        # Optionally: Inform user fetch failed
        # await client.send_message(chat_id=OWNER, text=f"⚠️ Failed to fetch links from {url}: {e}")
        return None # Return None on fetch errors
    except Exception as e:
        log.error(f"Unexpected error fetching/parsing links from {raw_url}: {e}", exc_info=True)
        # Optionally: Inform user fetch failed
        # await client.send_message(chat_id=OWNER, text=f"⚠️ Failed to parse links from {url}: {e}")
        return None # Return None on other errors

# --- End of function definition ---
# URL Handler: Modified to handle external link lists
# URL Handler: Modified to handle external link lists AND failed parsing
# Add this function definition inside __main__.py
async def ask_service_type(client, message):
     """Sends a new message asking for the download service type."""
     # Ensure OWNER is imported or accessible
     from colab_leecher import OWNER
     log = logging.getLogger(__name__)
     log.info("Asking user to select download service...")
     # Define keyboard
     keyboard_markup = InlineKeyboardMarkup([
          [InlineKeyboardButton("Aria", callback_data='service_direct'), InlineKeyboardButton("Debrid", callback_data='service_Debrid')],
          [InlineKeyboardButton("NZBCloud", callback_data='service_nzbcloud'), InlineKeyboardButton("Bitso", callback_data='service_bitso')],
          [InlineKeyboardButton("Downloadly", callback_data='service_downloadly')],
          [InlineKeyboardButton("Cancel Task", callback_data='cancel')]
     ])
     try:
         # --- FIX: Send a new message instead of editing ---
         # Reply to the user's message containing the links for context
         if message and hasattr(message, 'reply_text'):
              await message.reply_text(
                  "👇 **Select Download Service** for these links:",
                  reply_markup=keyboard_markup,
                  quote=True # Quote the user's link message
              )
         else:
              # Fallback if message context is somehow lost (shouldn't happen often)
              log.warning("ask_service_type: Message context lost, sending to OWNER.")
              await client.send_message(
                  OWNER,
                  "👇 **Select Download Service** for the links provided:",
                  reply_markup=keyboard_markup
              )
         # --- END FIX ---
     except Exception as e:
          log.error(f"Failed to ask service type: {e}", exc_info=True)
          # Try sending error message to owner as fallback
          try: await client.send_message(OWNER, f"⚠️ Error asking service type: {e}")
          except Exception: pass
# --- End ask_service_type function ---

# --- Replace the entire handle_url function ---
@colab_bot.on_message(filters.create(isLink) & ~filters.photo & filters.private)
async def handle_url(client: Client, message: Message):
    global BOT, src_request_msg, reply_prompt_message_id
    user_id = message.from_user.id

    # --- Initial State Checks ---
    # Handle extract waiting state FIRST (before command check)
    if BOT.State.extract_waiting:
        log.info(f"extract_waiting=True, processing path input: {message.text[:50] if message.text else 'None'}...")
        await _handle_extract_input(client, message)
        return

    # --- Safety Check: Ignore command messages (but allow file paths like /content/) ---
    if message.text and message.text.startswith('/'):
        # Check if it's actually a command (word followed by space or end of string)
        # vs a file path like /content/drive/...
        parts = message.text.split(None, 1)
        first_part = parts[0]
        has_more_slashes = '/' in first_part[1:]
        if len(parts[0]) <= 20 and not has_more_slashes:  # Commands are short, paths have more slashes
            log.debug("handle_url: Ignoring command message.")
            raise ContinuePropagation

    # Ignore if expecting filenames or waiting for mindvalley URLs
    if BOT.State.expecting_nzb_filenames or \
       BOT.State.expecting_Debrid_filenames or \
       BOT.State.expecting_bitso_filenames or \
       BOT.State.mindvalley_waiting:
        log.debug("handle_url: Ignoring link/path message - waiting for other input.")
        raise ContinuePropagation

    # Allow only owner input if task is started but not yet running
    if BOT.State.started and not BOT.State.task_going and user_id != OWNER:
        await message.reply_text("Bot is waiting for owner input.")
        return

    # Ignore if another task is actively running
    if BOT.State.task_going:
        log.warning("Task going, ignoring link/path in handle_url.")
        await message.reply_text("<i>🚨 Already working!</i>")
        return

    # Ignore if no task command was initiated
    if not BOT.State.started:
        log.warning("Task not started by command, ignoring link/path in handle_url.")
        await message.reply_text("<i>Start task with /tupload, /gdupload, or /drupload first.</i>")
        return
    # --- End Initial State Checks ---


    log.info(f"Handling URL/Path message from user {user_id}. Current Mode: {BOT.Mode.mode}")
    # Reset options initially
    BOT.Options.custom_name = ""; BOT.Options.zip_pswd = ""; BOT.Options.unzip_pswd = ""; BOT.Options.filenames = []; BOT.Options.service_type = None # Reset service type here

    # Delete the initial prompt message ("Send Me THEM LINK(s)...")
    if src_request_msg:
        try: await src_request_msg.delete(); src_request_msg = None
        except Exception as del_err: log.warning(f"Could not delete source request prompt: {del_err}"); src_request_msg = None

    try:
        input_text = message.text.strip() if message.text else ""
        if not input_text:
             await message.reply_text("❌ Input cannot be empty."); BOT.State.started = False; return

        # --- === Handle Directory Leech Path === ---
        if BOT.Mode.mode == "dir-leech":
            log.info(f"Processing input as directory path for dir-leech: '{input_text}'")
            # Check if path exists
            if not os.path.exists(input_text):
                 log.error(f"Dir-leech path does not exist: {input_text}")
                 await message.reply_text(f"❌ Path not found or invalid: `{input_text}`")
                 BOT.State.started = False # Reset state as input was invalid
                 return

            # Path is valid, store it
            BOT.SOURCE = [input_text]
            BOT.Options.service_type = "local" # Confirm service type
            log.info(f"Stored valid path for dir-leech. Source: {BOT.SOURCE}")

            # Dir-leech doesn't need service selection, proceed to leech type selection
            await ask_leech_type(client, message.chat.id, BOT.Mode.mode) # Ask normal/zip/unzip
            # The task will be scheduled after leech type is selected via callback

        # --- === Handle Normal Link Processing (Leech/Mirror Modes) === ---
        else:
            log.info("Processing input as URL(s) for leech/mirror mode...")
            urls = []
            extracted_args = {"custom_name": "", "zip_pswd": "", "unzip_pswd": ""}

            # Try fetching external links first
            parsed_links = None
            try: parsed_links = await fetch_links_from_url(input_text) # Ensure fetch_links_from_url is imported
            except Exception as fetch_err: log.error(f"Error during fetch_links_from_url call: {fetch_err}", exc_info=True)

            if parsed_links is not None: # Recognized as potential external list URL
                if not parsed_links:
                     log.warning(f"External URL '{input_text}' contained no valid links.")
                     await message.reply_text(f"❌ Found 0 valid links in the provided URL: {input_text}")
                     BOT.State.started = False; return
                log.info(f"Using {len(parsed_links)} links fetched from external URL: {input_text}")
                urls = parsed_links
            else:
                # Fallback: Process message directly for links and args
                log.info("Input not recognized as external list URL, processing directly.")
                # ... (existing logic for parsing links/args from message text) ...
                temp_source = [line.strip() for line in input_text.splitlines() if line.strip()]
                args_to_remove = 0
                for line in reversed(temp_source):
                     is_arg = False
                     if line.startswith("[") and line.endswith("]"): extracted_args["custom_name"] = line[1:-1]; is_arg = True
                     elif line.startswith("{") and line.endswith("}"): extracted_args["zip_pswd"] = line[1:-1]; is_arg = True
                     elif line.startswith("(") and line.endswith(")"): extracted_args["unzip_pswd"] = line[1:-1]; is_arg = True
                     if is_arg: args_to_remove += 1
                     else: break
                urls = temp_source[:-args_to_remove] if args_to_remove > 0 else temp_source

            # Set options from extracted args (only applies to direct message input)
            BOT.Options.custom_name = extracted_args["custom_name"]
            BOT.Options.zip_pswd = extracted_args["zip_pswd"]
            BOT.Options.unzip_pswd = extracted_args["unzip_pswd"]
            BOT.Options.filenames = [] # Reset filenames

            if not urls:
                log.warning("No valid URLs found after processing."); await message.reply_text("❌ No valid URLs found in the message."); BOT.State.started = False; return

            # Basic validation check (similar to previous version)
            standard_download_pattern = re.compile(r"^(https?://|magnet:\?|ftps?://)")
            paste_site_pattern = re.compile(r"pastebin\.com|gist\.github|rentry\.co|pastes\.io|pastie\.org")
            if parsed_links is None and len(urls) == 1 and urls[0] == input_text:
                if not standard_download_pattern.match(urls[0]) or paste_site_pattern.search(urls[0]):
                     log.error(f"Input '{input_text}' was not parsed and is not a direct download link.")
                     await message.reply_text(f"❌ Input is not a direct download link or a supported raw list URL: {input_text}")
                     BOT.State.started = False; return

            BOT.SOURCE = urls # Store the final list of links
            log.info(f"Received {len(BOT.SOURCE)} URLs for mode {BOT.Mode.mode} in handle_url.")

            # Ask for Service Type (only needed for leech/mirror link modes)
            await ask_service_type(client, message) # Ensure ask_service_type is imported

    except Exception as e:
        log.error(f"Error handling URL/Path message: {e}", exc_info=True)
        await message.reply_text(f"⚠️ Error processing input: {e}")
        BOT.State.started = False # Reset state on error
# --- End handle_url ---

@colab_bot.on_callback_query()
async def handle_options(client: Client, callback_query: CallbackQuery):
    global BOT, MSG, TaskError, TRANSFER, OWNER, DUMP_ID, src_request_msg, reply_prompt_message_id
    user_id = callback_query.from_user.id
    message = callback_query.message
    query_data = callback_query.data
    # Use message context safely
    msg_id = message.id if message else None
    chat_id = message.chat.id if message and hasattr(message, 'chat') else OWNER # Default to OWNER if chat missing

    # Authorization Checks (ensure correct indentation)
    if BOT.State.started and not BOT.State.task_going and user_id != OWNER:
        await callback_query.answer("Please wait for the owner...", show_alert=True)
        return
    if BOT.State.task_going and query_data == "cancel" and user_id != OWNER:
        await callback_query.answer("Only owner can cancel.", show_alert=True)
        return
    # Assuming settings callbacks start with "setting_" or similar prefixes handled later
    # Example check (adjust if needed):
    if query_data.startswith(("setting_", "video", "caption", "thumb", "set-suffix", "set-prefix", "close", "back")) and user_id != OWNER:
         await callback_query.answer("Owner only settings.", show_alert=True)
         return
    if not message:
        await callback_query.answer("Original message lost?", show_alert=True)
        log.error("Callback query failed: Message context lost.")
        return

    log.info(f"Handling callback query: {query_data} from user {user_id}")

    try: # Main try block starts here
        # --- Service Selection ---
        if query_data.startswith("service_"):
            await callback_query.answer() # Acknowledge first
            service = query_data.split("_", 1)[1]
            log.info(f"User selected service: {service}")
            BOT.Options.service_type = service

            # Delete the service selection message AFTER processing choice
            try:
                await message.delete()
            except Exception as e:
                log.warning(f"Could not delete service selection message: {e}")


            filenames_needed_choice = service in ["Debrid", "bitso", "nzbcloud"]
            # Downloadly and direct don't need filename choice, will auto-extract

            if filenames_needed_choice:
                log.info(f"Asking filename option for {service.capitalize()}")
                await ask_filename_option(client, chat_id, service.capitalize()) # Pass chat_id
            else:
                # No filename choice needed for this service
                log.info(f"Service '{service}' selected. Proceeding to ask leech type.")
                await ask_leech_type(client, chat_id, BOT.Mode.mode)

        # --- Filename Options ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE 'if' ABOVE >>>
        elif query_data.startswith("fn_"):
            await callback_query.answer()
            # Make sure service_type and fn_choice parsing is correct
            parts = query_data.split("_")
            if len(parts) < 3:
                 log.error(f"Invalid fn_ query data format: {query_data}")
                 await callback_query.answer("Internal error parsing choice.", show_alert=True)
                 return

            service_type = parts[1] # e.g., 'Debrid' or 'bitso'
            fn_choice = parts[2]    # e.g., 'extract' or 'manual'

            if fn_choice == "extract":
                log.info(f"User chose extract filenames for {service_type}.")
                extracted_filenames = []
                if not BOT.SOURCE:
                    await message.edit_text("❌ Error: No links found.")
                    BOT.State.started = False
                    return

                log.info(f"Extracting filenames for {len(BOT.SOURCE)} links...")
                all_extracted = True # Flag to track success
                for i, link in enumerate(BOT.SOURCE):
                    extracted_name = await extract_filename_from_url(link) # Use await
                    if extracted_name:
                        cleaned = apply_dot_style(clean_filename(extracted_name))
                        if cleaned: # Ensure cleaning didn't result in None
                             extracted_filenames.append(cleaned)
                             log.debug(f"Extracted and cleaned name for link {i+1}: {cleaned}")
                        else:
                             log.warning(f"Filename invalid after cleaning for link {i+1}: {link}. Aborting.")
                             await message.edit_text(f"❌ Error: Invalid filename after cleaning link #{i+1}. Task Cancelled.")
                             all_extracted = False; break # Stop loop
                    else:
                        log.warning(f"Failed to extract filename for link {i+1}: {link}. Aborting.")
                        await message.edit_text(f"❌ Error extracting filename for link #{i+1}. Task Cancelled.")
                        all_extracted = False; break # Stop loop

                if all_extracted:
                    BOT.Options.filenames = extracted_filenames
                    log.info(f"Extraction success: {len(extracted_filenames)} filenames.")
                    # Check if message still exists before deleting
                    if message: await message.delete() # Delete filename option message
                    await ask_leech_type(client, chat_id, BOT.Mode.mode) # Ask next step
                else:
                    # Extraction failed, reset relevant states
                    BOT.State.started = False; TaskError.reset(); TRANSFER.reset(); BOT.SOURCE=[]; BOT.Options.filenames=[] # Reset state

            elif fn_choice == "manual":
                log.info(f"User chose manual filenames for {service_type}.")
                expected_count = len(BOT.SOURCE)
                # This is where the prompt message is defined and sent:
                prompt_text = (f"📝 Okay, **reply to this message** with the {expected_count} filename(s) for {service_type.capitalize()}, one per line.\n\n"
                               f"**OR provide a link** (Gist/Pastebin/Rentry raw URL, or direct `.txt` link) containing the filenames.")
                try:
                    # Send the prompt
                    prompt_msg = await client.send_message(chat_id, prompt_text)
                    reply_prompt_message_id = prompt_msg.id # Store prompt ID
                    # Check if message still exists before deleting
                    if message: await message.delete() # Delete the button message
                    # Set state to expect reply
                    if service_type == 'Debrid': BOT.State.expecting_Debrid_filenames = True
                    elif service_type == 'bitso': BOT.State.expecting_bitso_filenames = True
                    elif service_type == 'nzbcloud': BOT.State.expecting_nzb_filenames = True    
                    # Add nzbcloud if needed: elif service_type == 'nzbcloud': BOT.State.expecting_nzb_filenames = True
                except Exception as e:
                    log.error(f"Failed to send manual filename prompt: {e}")
                    if message: await client.send_message(chat_id, f"❌ Error asking for filenames: {e}") # Use message if possible

            else:
                log.warning(f"Unknown filename choice: {fn_choice}")
                if message: await message.edit_text("⚠️ Unknown filename option.")

        # --- Leech Type Selection ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE 'if' AND 'elif' ABOVE >>>
        elif query_data.startswith("leechtype_"):
            await callback_query.answer()
            leech_type = query_data.split("_", 1)[1]
            log.info(f"User selected leech type: {leech_type}")
            BOT.Mode.type = leech_type
            if message: await message.delete() # Delete leech type selection message

            # --- REMOVED PASSWORD ASKING LOGIC FOR SIMPLICITY ---
            # Assuming passwords are set via commands /zipaswd /unzipaswd if needed

            # Directly schedule the task
            log.info("Proceeding to start task...")
            try: # Send status to OWNER
                # Ensure keyboard() is imported or defined if used here
                status_msg_obj = await client.send_message(OWNER, "#STARTING_TASK\n\n**Task commencing...**", reply_markup=keyboard())
                MSG.status_msg = status_msg_obj
            except Exception as start_err:
                log.error(f"Failed send status msg: {start_err}", exc_info=True)
                if message: await client.send_message(chat_id, "❌ Failed initialize task status.")
                BOT.State.started = False; BOT.State.task_going = False; return

            BOT.State.task_going = True; BOT.State.started = False; reply_prompt_message_id = None;
            BOT.TASK = asyncio.create_task(taskScheduler())
            # --- END REMOVED PASSWORD ASKING LOGIC ---

        # --- REMOVED Password Skipping Callbacks ---
        # Assuming passwords are now handled via commands only

        # --- Settings Callbacks ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        # Add settings callbacks here with correct indentation
        # Example:
        elif query_data == "setting_refresh":
             await callback_query.answer("Refreshing settings...")
             await send_settings(client, message, msg_id, False)
        elif query_data == "media":
             BOT.Options.stream_upload = True; BOT.Setting.stream_upload = "Media"
             await callback_query.answer("Uploading As Media", show_alert=False)
             await send_settings(client, message, msg_id, False)
        elif query_data == "document":
             BOT.Options.stream_upload = False; BOT.Setting.stream_upload = "Document"
             await callback_query.answer("Uploading As Document", show_alert=False)
             await send_settings(client, message, msg_id, False)
        # ... add other settings callbacks like "video", "caption", "thumb", "set-prefix", "set-suffix", "close", "back" ...
        # Ensure they all start with 'elif' and have the same indentation as the main 'if'/'elif' blocks
        elif query_data == "close":
            await callback_query.answer("Settings closed")
            await message.delete()
        elif query_data == "back":
            await callback_query.answer()
            await send_settings(client, message, msg_id, False)

        # --- Task Cancellation ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        elif query_data == "cancel" or query_data.startswith("cancel:"):
            # Parse callback data
            task_ctx = None
            if query_data.startswith("cancel:"):
                # Multi-task cancellation: extract task_id
                task_id = query_data.split(":", 1)[1]
                task_ctx = TASK_QUEUE.get_task(task_id)

                if not task_ctx:
                    await callback_query.answer("Task not found or already completed.", show_alert=True)
                    log.warning(f"Cancel requested for task {task_id[:8]} but not found in queue")
                    return

                log.info(f"Multi-task cancellation requested for task {task_ctx.get_short_id()}")
            else:
                # Legacy single-task cancellation
                log.info("Legacy task cancellation requested by user via button.")

            try:
                await callback_query.answer("Task Cancelled!", show_alert=True)
            except Exception:
                await callback_query.answer("Cancelling...") # Fallback answer

            if task_ctx:
                # Multi-task mode: cancel specific task
                log.info(f"Calling cancelTask for task {task_ctx.get_short_id()}")
                await cancelTask("User pressed Cancel button.", task_ctx=task_ctx)
                # Remove from queue
                TASK_QUEUE.remove_task(task_ctx.task_id)
                # Update summary dashboard
                await force_update_summary(client)
            else:
                # Legacy mode: global cancellation
                if BOT.State.started and not BOT.State.task_going:
                    log.info("Cancelling task during setup phase.")
                    BOT.State.started = False; reply_prompt_message_id = None;
                    if message: await message.delete() # Delete the message with the cancel button
                    # Reset states fully
                    TaskError.reset(); TRANSFER.reset(); BOT.SOURCE = []; BOT.Options.filenames = []
                elif BOT.State.task_going:
                    log.info("Calling cancelTask for running task.")
                    await cancelTask("User pressed Cancel button.")
                    # cancelTask handles deleting the status message
                else:
                    log.info("Cancel pressed but no task/setup active.")
                    if message: await message.delete() # Delete the message if it exists

                # Reset extract waiting state if active
                if BOT.State.extract_waiting:
                    log.info("Resetting extract waiting state")
                    BOT.State.extract_waiting = False
                    global extract_request_msg
                    if extract_request_msg:
                        try:
                            await extract_request_msg.delete()
                        except Exception:
                            pass
                        extract_request_msg = None

        # --- Fallback for Unknown Callbacks ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        else:
            log.warning(f"Unhandled callback query data: {query_data}")
            await callback_query.answer("Unknown action!", show_alert=True)

    # This 'except' MUST be aligned with the 'try' block at the start of the function
    except Exception as e:
        log.error(f"Error handling callback {query_data}: {e}", exc_info=True)
        try:
            await callback_query.answer("An error occurred!", show_alert=True)
        except Exception: pass # Ignore if answering fails too
        # Reset state fully on unhandled error
        BOT.State.started = False; BOT.State.task_going = False; reply_prompt_message_id = None;
        if TaskError: TaskError.reset()
        if TRANSFER: TRANSFER.reset()
        BOT.SOURCE = []; BOT.Options.filenames = []

# --- End handle_options function ---
# Image Handler (handle_image - remains the same)
@colab_bot.on_message(filters.photo & filters.private)
async def handle_image(client, message):
    log.info(f"Received photo from user {message.from_user.id}, setting thumbnail.")
    msg = await message.reply_text("<i>Trying To Save Thumbnail...</i>")
    success = await setThumbnail(message)
    if success: await msg.edit_text("**Thumbnail Changed ✅**"); await message.delete()
    else: await msg.edit_text("🥲 **Couldn’t set thumbnail...**", quote=True)
    await sleep(5); await message_deleter(None, msg)

# Other Command Handlers (setname, zipaswd, unzipaswd, help - remain the same)
@colab_bot.on_message(filters.command("setname") & filters.private)
async def custom_name(client, message):
    global BOT; log.info("Received /setname command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/setname <code>custom_fileame.extension</code>", quote=True)
    else: BOT.Options.custom_name = message.command[1]; msg = await message.reply_text("Custom Name Set!"); log.info(f"Custom name: {BOT.Options.custom_name}")
    await sleep(15); await message_deleter(message, msg)
@colab_bot.on_message(filters.command("zipaswd") & filters.private)
async def zip_pswd(client, message):
    global BOT; log.info("Received /zipaswd command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/zipaswd <code>password</code>", quote=True)
    else: BOT.Options.zip_pswd = message.command[1]; msg = await message.reply_text("Zip Password Set!"); log.info("Zip password set.")
    await sleep(15); await message_deleter(message, msg)
@colab_bot.on_message(filters.command("unzipaswd") & filters.private)
async def unzip_pswd(client, message):
    global BOT; log.info("Received /unzipaswd command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/unzipaswd <code>password</code>", quote=True)
    else: BOT.Options.unzip_pswd = message.command[1]; msg = await message.reply_text("Unzip Password Set!"); log.info("Unzip password set.")
    await sleep(15); await message_deleter(message, msg)

# Helper function to perform extraction
async def _perform_extraction(archive_path, file_filter=None):
    """
    Core extraction logic with streaming upload - returns (success: bool, message: str)
    Extracts files one-by-one, uploads to Telegram, then deletes temp file
    """
    from .utility.converters import extract_and_upload_streaming
    import os

    # Determine archive type
    ext = os.path.splitext(archive_path)[1].lower()
    filename = os.path.basename(archive_path)

    # Start extraction based on archive type
    try:
        if ext == ".rar" or ".part" in filename.lower():
            log.info(f"Starting streaming extract+upload for RAR: {archive_path}")

            # Use streaming extract+upload (extracts one file, uploads it, deletes temp file)
            success = await extract_and_upload_streaming(
                rar_filepath=archive_path,
                password=BOT.Options.unzip_pswd if BOT.Options.unzip_pswd else None,
                file_filter=file_filter,
                task_ctx=None
            )

            if success:
                msg = (
                    f"✅ Extraction + Upload complete!\n\n"
                    f"📁 Archive: `{filename}`\n"
                    f"⬆️ All files uploaded to Telegram\n"
                    f"🗑️ Temp files cleaned up"
                )
                log.info(f"Streaming extract+upload successful: {archive_path}")
                return True, msg
            else:
                log.error(f"Streaming extract+upload failed: {archive_path}")
                return False, f"❌ Extraction/Upload failed!\n\nCheck logs for details."

        elif ext == ".zip":
            log.error(f"ZIP streaming not yet implemented: {archive_path}")
            return False, f"❌ ZIP streaming extract+upload not yet implemented\n\nUse RAR archives for now"
        else:
            return False, f"❌ Unsupported format: {ext}\n\nSupported: .rar (streaming), .zip (coming soon)"

    except Exception as e:
        log.error(f"Extraction error: {e}", exc_info=True)
        return False, f"❌ Extraction error: {str(e)[:100]}"

# Helper function to process reply-to-document extraction
async def _process_extract_reply(client, message):
    """Handle extraction when user replies to a document"""
    global BOT, Paths, MSG
    import os
    import random
    import aiohttp
    import aiofiles
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard

    # Parse file filter from command if provided
    file_filter = None
    if len(message.command) > 1:
        extensions_str = ' '.join(message.command[1:])
        extensions = [ext.strip() for ext in extensions_str.split(',')]
        file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
        log.info(f"File filter applied: {file_filter}")

    try:
        reply_msg = await message.reply_text("⬇️ Downloading archive...")
        file_path = await message.reply_to_message.download(
            file_name=os.path.join(Paths.down_path, message.reply_to_message.document.file_name)
        )

        # Download random thumbnail
        hero_image_path = Paths.HERO_IMAGE
        download_success = False

        if thumbnail_urls:
            try:
                chosen_url = random.choice(thumbnail_urls)
                log.info(f"Downloading thumbnail for extraction: {chosen_url}")

                async with aiohttp.ClientSession() as session:
                    async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            async with aiofiles.open(hero_image_path, mode='wb') as f:
                                while True:
                                    chunk = await response.content.read(1024)
                                    if not chunk:
                                        break
                                    await f.write(chunk)
                            download_success = True
            except Exception as e:
                log.warning(f"Thumbnail download failed: {e}")

        # Determine thumbnail path
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH
        elif download_success and os.path.exists(Paths.HERO_IMAGE):
            thumb_path = Paths.HERO_IMAGE
        elif os.path.exists(Paths.DEFAULT_HERO):
            thumb_path = Paths.DEFAULT_HERO
        else:
            thumb_path = None

        # Create extraction status message
        filename = os.path.basename(file_path)
        filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

        status_text = (
            f"<b>📂 Archive Extraction »</b>\n\n"
            f"<b>📦 Archive:</b> <code>{filename}</code>\n"
            f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
            f"<i>Initializing...</i>"
        )

        # Replace reply message with photo message
        await reply_msg.delete()

        if thumb_path and os.path.exists(thumb_path):
            status_msg = await client.send_photo(
                message.chat.id,
                photo=thumb_path,
                caption=status_text,
                reply_markup=keyboard()
            )
        else:
            status_msg = await message.reply_text(status_text)

        # Link to global MSG.status_msg
        MSG.status_msg = status_msg

        success, result_msg = await _perform_extraction(file_path, file_filter)

        # Update final message
        if hasattr(status_msg, 'photo') and status_msg.photo:
            await status_msg.edit_caption(caption=result_msg)
        else:
            await status_msg.edit_text(result_msg)

    except Exception as e:
        log.error(f"Failed to download/extract replied file: {e}")
        await message.reply_text(f"❌ Failed: {str(e)[:100]}")

# Helper function to handle extract path input from user
async def _handle_extract_input(client, message):
    """Process user's path input after /extract command"""
    global BOT, Paths, MSG, extract_request_msg
    import os
    import re
    import random
    import aiohttp
    import aiofiles
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard

    # Reset state
    BOT.State.extract_waiting = False

    # Delete the prompt message
    if extract_request_msg:
        try:
            await extract_request_msg.delete()
            extract_request_msg = None
        except Exception:
            pass

    # Parse input: "<path>" or "<path> <filter>"
    input_text = message.text.strip() if message.text else ""
    if not input_text:
        await message.reply_text("❌ Input cannot be empty. Use /extract to try again.")
        return

    # Split into path and optional filter
    parts = input_text.split(None, 1)  # Split on first whitespace
    archive_path = parts[0]
    file_filter = None

    if len(parts) > 1:
        # User provided filter
        extensions_str = parts[1]
        extensions = [ext.strip() for ext in extensions_str.split(',')]
        file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
        log.info(f"File filter applied: {file_filter}")

    # Validate path exists
    if not os.path.exists(archive_path) or not os.path.isfile(archive_path):
        await message.reply_text(f"❌ File not found: `{archive_path}`\n\nUse /extract to try again.")
        return

    # Auto-detect first part for multi-part RAR (handles formats like part01.rar or part01_Downloadly.ir.rar)
    if '.part' in archive_path.lower() and archive_path.lower().endswith('.rar'):
        # Extract base name and suffix (e.g., "_Downloadly.ir.rar" or ".rar")
        match = re.search(r'(.*)\.part\d+(.*\.rar)$', archive_path, flags=re.IGNORECASE)
        if match:
            base = match.group(1)
            suffix = match.group(2)  # Captures everything after partXX (e.g., ".rar" or "_Downloadly.ir.rar")

            potential_first_parts = [
                f"{base}.part01{suffix}",
                f"{base}.part001{suffix}",
                f"{base}.part1{suffix}"
            ]
            for first_part in potential_first_parts:
                if os.path.exists(first_part):
                    archive_path = first_part
                    log.info(f"Multi-part RAR detected, using first part: {archive_path}")
                    break

    # Download random thumbnail (following Mindvalley pattern)
    hero_image_path = Paths.HERO_IMAGE
    download_success = False

    if thumbnail_urls:
        try:
            chosen_url = random.choice(thumbnail_urls)
            log.info(f"Downloading thumbnail for extraction: {chosen_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        download_success = True
                        log.info(f"Thumbnail downloaded to {hero_image_path}")
        except Exception as e:
            log.warning(f"Thumbnail download failed: {e}")

    # Determine thumbnail path (priority: custom > random > default)
    if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
    elif download_success and os.path.exists(Paths.HERO_IMAGE):
        thumb_path = Paths.HERO_IMAGE
    elif os.path.exists(Paths.DEFAULT_HERO):
        thumb_path = Paths.DEFAULT_HERO
    else:
        thumb_path = None

    # Create status message
    filename = os.path.basename(archive_path)
    filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

    status_text = (
        f"<b>📂 Archive Extraction »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{filename}</code>\n"
        f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
        f"<i>Initializing...</i>"
    )

    # Send message with thumbnail
    if thumb_path and os.path.exists(thumb_path):
        status_msg = await client.send_photo(
            message.chat.id,
            photo=thumb_path,
            caption=status_text,
            reply_markup=keyboard()
        )
    else:
        status_msg = await message.reply_text(status_text)

    # Link to global MSG.status_msg for progress updates
    MSG.status_msg = status_msg

    # Perform extraction
    success, result_msg = await _perform_extraction(archive_path, file_filter)

    # Update final message
    if hasattr(status_msg, 'photo') and status_msg.photo:
        await status_msg.edit_caption(caption=result_msg)
    else:
        await status_msg.edit_text(result_msg)

@colab_bot.on_message(filters.command("extract") & filters.private)
async def extract_archive(client, message):
    """
    Extract RAR/ZIP archive with optional file filtering

    Usage:
        /extract - Prompt for archive path
        /extract .mkv - Extract only .mkv files from recent download
        /extract .mkv,.mp4,.avi - Extract multiple file types
        /extract /path/to/file.rar - Extract from specific path
        /extract /path/to/file.rar .mkv - Extract specific path with filter
        Reply to archive: Reply to RAR/ZIP file with /extract [filter]
    """
    global BOT, Paths, MSG, extract_request_msg
    from .utility.converters import extract_rar_streaming, extract_zip_streaming
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard
    import os
    import random
    import aiohttp
    import aiofiles

    log.info(f"Received /extract from {message.from_user.id}")

    # Check if user is replying to a document (takes priority)
    if message.reply_to_message and message.reply_to_message.document:
        # Process reply-to-document immediately with optional filter from command
        await _process_extract_reply(client, message)
        return

    # If no arguments provided, ask for path
    if len(message.command) == 1:
        log.info("No arguments provided, setting extract_waiting=True and prompting for path")
        BOT.State.extract_waiting = True
        help_text = (
            "📂 **Extract Archive**\n\n"
            "Send me the archive path and optional file filter:\n\n"
            "**Examples:**\n"
            "`/content/drive/MyDrive/file.part01.rar`\n"
            "`/content/drive/MyDrive/file.rar .mkv`\n"
            "`/content/drive/MyDrive/file.zip .mkv,.mp4`\n\n"
            "**Format:**\n"
            "`<path>` or `<path> <filter>`\n\n"
            "Cancel with /cancel"
        )
        extract_request_msg = await message.reply_text(help_text)
        return

    # Parse command arguments (file path and/or filters)
    file_filter = None
    explicit_path = None

    if len(message.command) > 1:
        # Check if first argument is a file path
        first_arg = message.command[1]

        # Detect if it's a file path (contains / or \ or ends with archive extension)
        if ('/' in first_arg or '\\' in first_arg or
            first_arg.lower().endswith(('.rar', '.zip', '.part01.rar', '.part001.rar', '.part1.rar'))):
            explicit_path = first_arg
            log.info(f"Explicit path provided: {explicit_path}")

            # Check if there are additional arguments for file filter
            if len(message.command) > 2:
                # Remaining arguments are file filters
                extensions_str = ' '.join(message.command[2:])
                extensions = [ext.strip() for ext in extensions_str.split(',')]
                file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
                log.info(f"File filter applied: {file_filter}")
        else:
            # First argument is a file filter, not a path
            extensions_str = ' '.join(message.command[1:])
            extensions = [ext.strip() for ext in extensions_str.split(',')]
            file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
            log.info(f"File filter applied: {file_filter}")

    # Try to find archive file
    archive_path = None

    # Method 0: Check if explicit path was provided
    if explicit_path:
        if os.path.exists(explicit_path) and os.path.isfile(explicit_path):
            archive_path = explicit_path
            log.info(f"Using explicit path: {archive_path}")

            # If it's a multi-part RAR but not the first part, try to find part01 (handles Downloadly format)
            if '.part' in archive_path.lower() and archive_path.lower().endswith('.rar'):
                # Extract base name and suffix (e.g., "_Downloadly.ir.rar" or ".rar")
                import re
                match = re.search(r'(.*)\.part\d+(.*\.rar)$', archive_path, flags=re.IGNORECASE)
                if match:
                    base = match.group(1)
                    suffix = match.group(2)  # Captures everything after partXX

                    # Try different naming conventions
                    potential_first_parts = [
                        f"{base}.part01{suffix}",
                        f"{base}.part001{suffix}",
                        f"{base}.part1{suffix}"
                    ]

                    for first_part in potential_first_parts:
                        if os.path.exists(first_part):
                            archive_path = first_part
                            log.info(f"Multi-part RAR detected, using first part: {archive_path}")
                            break
        else:
            await message.reply_text(f"❌ File not found: `{explicit_path}`")
            return

    # Method 1: Check for most recent archive in download directory
    if not archive_path and os.path.exists(Paths.down_path):
        try:
            # Find most recent .rar or .zip file
            archive_files = []
            for f in os.listdir(Paths.down_path):
                if f.lower().endswith(('.rar', '.zip', '.part01.rar', '.part001.rar', '.part1.rar')):
                    full_path = os.path.join(Paths.down_path, f)
                    if os.path.isfile(full_path):
                        archive_files.append((full_path, os.path.getmtime(full_path)))

            if archive_files:
                # Sort by modification time (most recent first)
                archive_files.sort(key=lambda x: x[1], reverse=True)
                archive_path = archive_files[0][0]
                log.info(f"Using most recent archive: {archive_path}")
        except Exception as e:
            log.error(f"Error finding archive: {e}")

    if not archive_path:
        # No archive found - prompt user to send path manually
        BOT.State.extract_waiting = True
        help_text = (
            "📂 **Extract Archive**\n\n"
            "❌ No recent archive found in downloads.\n\n"
            "Send me the archive path and optional file filter:\n\n"
            "**Examples:**\n"
            "`/content/drive/MyDrive/file.part01.rar`\n"
            "`/content/drive/MyDrive/file.rar .mkv`\n"
            "`/content/drive/MyDrive/file.zip .mkv,.mp4`\n\n"
            "**Format:**\n"
            "`<path>` or `<path> <filter>`\n\n"
            "Cancel with /cancel"
        )
        extract_request_msg = await message.reply_text(help_text)
        return

    # Download random thumbnail
    hero_image_path = Paths.HERO_IMAGE
    download_success = False

    if thumbnail_urls:
        try:
            chosen_url = random.choice(thumbnail_urls)
            log.info(f"Downloading thumbnail for extraction: {chosen_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        download_success = True
                        log.info(f"Thumbnail downloaded to {hero_image_path}")
        except Exception as e:
            log.warning(f"Thumbnail download failed: {e}")

    # Determine thumbnail path (priority: custom > random > default)
    if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
    elif download_success and os.path.exists(Paths.HERO_IMAGE):
        thumb_path = Paths.HERO_IMAGE
    elif os.path.exists(Paths.DEFAULT_HERO):
        thumb_path = Paths.DEFAULT_HERO
    else:
        thumb_path = None

    # Create status message
    filename = os.path.basename(archive_path)
    filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

    status_text = (
        f"<b>📂 Archive Extraction »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{filename}</code>\n"
        f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
        f"<i>Initializing...</i>"
    )

    # Send message with thumbnail
    if thumb_path and os.path.exists(thumb_path):
        status_msg = await client.send_photo(
            message.chat.id,
            photo=thumb_path,
            caption=status_text,
            reply_markup=keyboard()
        )
    else:
        status_msg = await message.reply_text(status_text)

    # Link to global MSG.status_msg for progress updates
    MSG.status_msg = status_msg

    # Perform extraction using helper function
    success, result_msg = await _perform_extraction(archive_path, file_filter)

    # Update final message
    if hasattr(status_msg, 'photo') and status_msg.photo:
        await status_msg.edit_caption(caption=result_msg)
    else:
        await status_msg.edit_text(result_msg)

@colab_bot.on_message(filters.command("mindvalley") & filters.private)
async def mindvalley_download(client, message):
    """
    Download Mindvalley course streams from M3U8 URLs
    Usage: /mindvalley then send URLs on separate lines
    """
    global BOT, src_request_msg
    log.info(f"Received /mindvalley from {message.from_user.id}")

    # Set bot state and mode
    BOT.Mode.mode = "leech"  # Use leech mode for proper completion message
    BOT.Mode.ytdl = False
    BOT.Options.service_type = "mindvalley"  # Track service type
    BOT.State.mindvalley_waiting = True

    help_text = (
        "**🎬 Mindvalley Course Downloader**\n\n"
        "**Send your M3U8 URLs** (choose one option):\n\n"
        "**Option 1:** Full download (video + audio + subtitle)\n"
        "`TITLE=My Lesson Name` (optional - for custom filename)\n"
        "`https://...video.m3u8`\n"
        "`https://...audio.m3u8` (optional)\n"
        "`https://...subtitle.webvtt.m3u8` (optional)\n\n"
        "**Option 2:** Subtitle-only download ⚠️ Must use flag!\n"
        "`DOWNLOAD_TYPE=subtitle-only` (required!)\n"
        "`TITLE=My Subtitle Name` (optional)\n"
        "`https://...subtitle.webvtt.m3u8`\n\n"
        "**Option 3:** Raw gist URL (with TITLE= as first line)\n"
        "`https://gist.githubusercontent.com/...`\n\n"
        "📌 **Tip:** Use browser extension to auto-copy with title!\n"
        "💡 **Tip:** Put long URLs in a gist to avoid character limits!\n"
        "📝 **Note:** Subtitles uploaded as both SRT and VTT formats"
    )
    src_request_msg = await task_starter(message, help_text)
    log.debug(f"/mindvalley: task_starter called, src_request_msg set")


# Handler for Mindvalley URLs (when user sends URLs after /mindvalley command)
@colab_bot.on_message(filters.text & filters.private)
async def handle_mindvalley_urls(client, message):
    """Handle URLs sent after /mindvalley command (supports direct M3U8 URLs or gist URLs)"""
    global BOT, MSG, src_request_msg, Messages, BotTimes

    # Check if we're waiting for Mindvalley URLs
    if not BOT.State.mindvalley_waiting:
        return  # Not in Mindvalley mode, let other handlers process this

    log.info(f"Received Mindvalley input from {message.from_user.id}")

    # Reset the flag
    BOT.State.mindvalley_waiting = False

    # Delete the help/request message
    if src_request_msg:
        try:
            await src_request_msg.delete()
            src_request_msg = None
        except Exception:
            pass

    # NEW: Create TaskContext for this download (enables parallel tasks)
    task_ctx = create_task_context(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "mindvalley"
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for Mindvalley download")

    try:
        input_text = message.text.strip()
        urls = []
        custom_title = None  # Store custom title from TITLE= line
        subtitle_only = False  # NEW: Flag for subtitle-only mode

        # Check if input is a gist URL
        if 'gist.githubusercontent.com' in input_text or 'gist.github.com' in input_text:
            log.info(f"Detected gist URL: {input_text}")

            # Convert to raw URL if needed
            raw_url = input_text
            if 'gist.github.com' in input_text and '/raw' not in input_text:
                # User sent the normal gist URL, convert to raw
                await message.reply_text("⚠️ Please use the **RAW** gist URL. Click 'Raw' button on gist page.", quote=True)
                return

            # Fetch content from gist
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(raw_url, timeout=20) as response:
                        response.raise_for_status()
                        gist_content = await response.text()

                        # Parse M3U8 URLs from gist
                        lines = gist_content.strip().split('\n')
                        for line in lines:
                            line = line.strip()

                            # Check for TITLE= line (case-insensitive)
                            if line.upper().startswith('TITLE='):
                                custom_title = line.split('=', 1)[1].strip()
                                log.info(f"Extracted custom title from gist: {custom_title}")
                                continue  # Skip this line, don't add to URLs

                            # NEW: Check for DOWNLOAD_TYPE=subtitle-only
                            if line.upper().startswith('DOWNLOAD_TYPE='):
                                download_type = line.split('=', 1)[1].strip().lower()
                                if download_type == 'subtitle-only' or download_type == 'subtitle_only':
                                    subtitle_only = True
                                    log.info("Subtitle-only mode enabled via DOWNLOAD_TYPE")
                                continue  # Skip this line, don't add to URLs

                            # Support both direct URLs and KEY=VALUE format
                            # Accept .m3u8 or .webvtt.m3u8 (for subtitles)
                            if '.m3u8' in line.lower() or '.webvtt' in line.lower():
                                if '=' in line:  # Format: VIDEO_URL=https://...
                                    url = line.split('=', 1)[1].strip()
                                else:  # Direct URL format
                                    url = line
                                urls.append(url)

                        log.info(f"Fetched {len(urls)} M3U8 URLs from gist")
            except Exception as fetch_err:
                log.error(f"Failed to fetch gist: {fetch_err}")
                await message.reply_text(f"❌ Failed to fetch gist: {str(fetch_err)}", quote=True)
                return

        # Direct M3U8 URLs input (including .webvtt.m3u8 for subtitles)
        elif '.m3u8' in input_text.lower() or '.webvtt' in input_text.lower() or input_text.upper().startswith('TITLE=') or input_text.upper().startswith('DOWNLOAD_TYPE='):
            lines = input_text.split('\n')
            for line in lines:
                line = line.strip()

                # Check for TITLE= line (case-insensitive)
                if line.upper().startswith('TITLE='):
                    custom_title = line.split('=', 1)[1].strip()
                    log.info(f"Extracted custom title from input: {custom_title}")
                    continue  # Skip this line, don't add to URLs

                # Check for DOWNLOAD_TYPE=subtitle-only
                if line.upper().startswith('DOWNLOAD_TYPE='):
                    download_type = line.split('=', 1)[1].strip().lower()
                    if download_type == 'subtitle-only' or download_type == 'subtitle_only':
                        subtitle_only = True
                        log.info("Subtitle-only mode enabled via DOWNLOAD_TYPE")
                    continue  # Skip this line, don't add to URLs

                # Accept M3U8 URLs (including .webvtt.m3u8 for subtitles)
                if line and ('.m3u8' in line.lower() or '.webvtt' in line.lower()):
                    urls.append(line)

            log.info(f"Parsed {len(urls)} direct M3U8 URLs")

        else:
            await message.reply_text("❌ Please send either M3U8 URLs or a raw gist URL.", quote=True)
            return

        if not urls:
            await message.reply_text("❌ No valid M3U8 URLs found. Please try again.", quote=True)
            return

        # Parse URLs based on mode
        if subtitle_only:
            # Subtitle-only mode: first (and only) URL is subtitle
            subtitle_url = urls[0] if len(urls) > 0 else None
            video_url = None
            audio_url = None

            # Validate subtitle URL (accepts .m3u8 or .webvtt.m3u8)
            if not subtitle_url or ('.m3u8' not in subtitle_url.lower() and '.webvtt' not in subtitle_url.lower()):
                await message.reply_text(
                    "❌ Invalid subtitle URL. Must be a valid M3U8 or WebVTT playlist URL (.m3u8 or .webvtt.m3u8).",
                    quote=True
                )
                return
        else:
            # Normal mode: video, optional audio, optional subtitle
            video_url = urls[0] if len(urls) > 0 else None
            audio_url = urls[1] if len(urls) > 1 else None
            subtitle_url = urls[2] if len(urls) > 2 else None

            # Validate video URL
            if not video_url or ('.m3u8' not in video_url.lower()):
                await message.reply_text(
                    "❌ Invalid video URL. First line must be a valid M3U8 playlist URL.",
                    quote=True
                )
                return

        # NEW: Create unique directories for this task
        os.makedirs(task_ctx.work_path, exist_ok=True)
        os.makedirs(task_ctx.down_path, exist_ok=True)
        log.info(f"Created task-specific directories: {task_ctx.work_path}")

        # Create downloader instance with task context
        downloader = MindvalleyDownloader(client, message, task_ctx)

        # Generate output filename
        if custom_title:
            # Use custom title from TITLE= line
            base_name = clean_filename(custom_title)
            # Apply dot style for consistency with other downloads
            base_name = apply_dot_style(base_name) if base_name else "mindvalley_course"
            # Ensure correct extension based on mode
            if subtitle_only:
                output_filename = base_name if base_name.lower().endswith('.vtt') else f"{base_name}.vtt"
            else:
                output_filename = base_name if base_name.lower().endswith('.mp4') else f"{base_name}.mp4"
            log.info(f"Using custom filename from title: {output_filename}")
        else:
            # Fallback to timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if subtitle_only:
                output_filename = f"mindvalley_subtitle_{timestamp}.vtt"
            else:
                output_filename = f"mindvalley_course_{timestamp}.mp4"
            log.info(f"Using timestamp filename: {output_filename}")

        # Store URLs in task context
        task_ctx.source_urls = urls
        task_ctx.filenames = [output_filename]

        # Initialize status message for progress tracking
        if subtitle_only:
            status_text = (
                f"📝 **Mindvalley Subtitle Download** [{task_ctx.get_short_id()}]\n\n"
                f"📝 Subtitle: ✅\n"
                f"📹 Video: ❌ (subtitle-only mode)\n"
                f"🔊 Audio: ❌ (subtitle-only mode)\n\n"
                f"_Download will start shortly..._"
            )
        else:
            status_text = (
                f"🎬 **Mindvalley Download Started** [{task_ctx.get_short_id()}]\n\n"
                f"📹 Video: ✅\n"
                f"🔊 Audio: {'✅' if audio_url else '❌ (using embedded audio)'}\n"
                f"📝 Subtitle: {'✅' if subtitle_url else '❌'}\n\n"
                f"_Download will start shortly..._"
            )

        # Download random thumbnail - use shared pool from task_manager
        # Import the full thumbnail collection (~472 URLs) instead of hardcoded subset
        from .utility.task_manager import thumbnail_urls

        # NEW: Use task-specific hero image path
        hero_image_path = task_ctx.hero_image
        chosen_url = random.choice(thumbnail_urls) if thumbnail_urls else Aria2c.pic_dwn_url

        log.info(f"Downloading random thumbnail for task {task_ctx.get_short_id()}: {chosen_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=30) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        if os.path.exists(hero_image_path):
                            log.info(f"Random thumbnail downloaded to {hero_image_path}")
                        else:
                            log.warning(f"Thumbnail download failed: file not found")
                    else:
                        log.warning(f"Thumbnail download failed: HTTP {response.status}")
        except Exception as e:
            log.error(f"Error downloading random thumbnail: {e}")

        # Get thumbnail path (priority: custom > random downloaded > static default)
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH  # Use custom thumbnail
        elif os.path.exists(task_ctx.hero_image):
            thumb_path = task_ctx.hero_image  # Use task-specific random thumbnail
        else:
            thumb_path = Paths.DEFAULT_HERO  # Fallback to static default

        # Send status message with thumbnail (store in task_ctx, not global MSG)
        if os.path.exists(thumb_path):
            task_ctx.status_msg = await client.send_photo(
                OWNER,
                photo=thumb_path,
                caption=status_text,
                reply_markup=keyboard(task_ctx.task_id)  # Add cancel button with task ID
            )
            log.info(f"Sent Mindvalley status with thumbnail: {thumb_path} (task {task_ctx.get_short_id()})")
        else:
            # Fallback to text if no thumbnail exists
            log.warning(f"Thumbnail not found at {thumb_path}, sending text message")
            task_ctx.status_msg = await client.send_message(
                OWNER,
                status_text,
                reply_markup=keyboard(task_ctx.task_id)  # Add cancel button with task ID
            )

        # Also set global MSG for backward compatibility with status_bar()
        # TODO: Remove this in Phase 3 when status_bar() is refactored
        MSG.status_msg = task_ctx.status_msg

        # Set task message for completion (in task_ctx)
        task_ctx.messages.task_msg = f"<b>TASK MODE » </b><i>Mindvalley Leech</i>\n\n"
        task_ctx.messages.src_link = f"https://gist.githubusercontent.com/..." if 'gist' in input_text else "M3U8 URLs"
        task_ctx.messages.download_name = output_filename

        # Also set globals for backward compat
        MSG.task_msg = task_ctx.messages.task_msg
        MSG.src_link = task_ctx.messages.src_link
        MSG.download_name = output_filename

        # NEW: Define async task function for parallel execution
        async def run_mindvalley_task():
            """Async task function that runs download+upload in the background"""
            try:
                task_ctx.mark_started()
                BotTimes.start_time = datetime.now()
                log.info(f"Task {task_ctx.get_short_id()} started: Mindvalley download")

                # Download based on mode
                vtt_path = None
                srt_path = None
                if subtitle_only:
                    # Returns (success, vtt_path, srt_path) - no final_path for subtitle-only
                    success, vtt_path, srt_path = await downloader.download_subtitle_only(
                        subtitle_url, output_filename
                    )
                    # For subtitle-only, set final_path to vtt_path for backward compatibility
                    final_path = vtt_path if success else None
                else:
                    # Returns (success, mp4_path, vtt_path, srt_path)
                    success, final_path, vtt_path, srt_path = await downloader.download_and_merge(
                        video_url, audio_url, subtitle_url, output_filename
                    )

                if success and final_path:
                    try:
                        # Handle subtitle-only mode differently
                        if subtitle_only:
                            log.info(f"Task {task_ctx.get_short_id()}: Uploading subtitle files...")
                            upload_success = True  # Will be set to False if uploads fail

                            # Upload SRT file (more compatible) using upload_file for proper stats tracking
                            if srt_path and os.path.exists(srt_path):
                                srt_display_name = os.path.basename(srt_path)
                                log.info(f"Uploading SRT subtitle: {srt_display_name}")
                                srt_upload = await upload_file(srt_path, srt_display_name, task_ctx)
                                if srt_upload:
                                    log.info(f"SRT file uploaded successfully: {srt_display_name}")
                                    try:
                                        os.remove(srt_path)
                                        log.info(f"Cleaned up SRT file: {srt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up SRT file: {cleanup_err}")
                                else:
                                    log.error(f"SRT upload failed: {srt_display_name}")
                                    upload_success = False

                            # Upload VTT file (original) using upload_file for proper stats tracking
                            if vtt_path and os.path.exists(vtt_path):
                                vtt_display_name = os.path.basename(vtt_path)
                                log.info(f"Uploading VTT subtitle: {vtt_display_name}")
                                vtt_upload = await upload_file(vtt_path, vtt_display_name, task_ctx)
                                if vtt_upload:
                                    log.info(f"VTT file uploaded successfully: {vtt_display_name}")
                                    try:
                                        os.remove(vtt_path)
                                        log.info(f"Cleaned up VTT file: {vtt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up VTT file: {cleanup_err}")
                                else:
                                    log.error(f"VTT upload failed: {vtt_display_name}")
                                    upload_success = False

                        else:
                            # Normal mode: Upload MP4 video
                            log.info(f"Task {task_ctx.get_short_id()}: Uploading {final_path} to Telegram...")
                            display_name = os.path.basename(final_path)
                            upload_success = await upload_file(final_path, display_name, task_ctx)

                        # If successful and we have subtitle files, upload them using upload_file
                        if upload_success:
                            # Upload SRT file (more widely compatible) using upload_file for proper stats tracking
                            if srt_path and os.path.exists(srt_path):
                                log.info(f"Task {task_ctx.get_short_id()}: Uploading SRT subtitle {srt_path}...")
                                srt_display_name = os.path.basename(srt_path)

                                srt_upload = await upload_file(srt_path, srt_display_name, task_ctx)
                                if srt_upload:
                                    log.info(f"SRT file uploaded successfully: {srt_display_name}")
                                    # Clean up SRT file after upload
                                    try:
                                        os.remove(srt_path)
                                        log.info(f"Cleaned up SRT file: {srt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up SRT file: {cleanup_err}")
                                else:
                                    log.error(f"Failed to upload SRT file: {srt_display_name}")
                                    # Continue to VTT upload

                            # Upload VTT file (original format) using upload_file for proper stats tracking
                            if vtt_path and os.path.exists(vtt_path):
                                log.info(f"Task {task_ctx.get_short_id()}: Uploading VTT subtitle {vtt_path}...")
                                vtt_display_name = os.path.basename(vtt_path)

                                vtt_upload = await upload_file(vtt_path, vtt_display_name, task_ctx)
                                if vtt_upload:
                                    log.info(f"VTT file uploaded successfully: {vtt_display_name}")
                                    # Clean up VTT file after upload
                                    try:
                                        os.remove(vtt_path)
                                        log.info(f"Cleaned up VTT file: {vtt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up VTT file: {cleanup_err}")
                                else:
                                    log.error(f"Failed to upload VTT file: {vtt_display_name}")
                                    # Continue anyway - main file was uploaded

                        if upload_success:
                            # Pass task_ctx to SendLogs for per-task completion tracking
                            await SendLogs(is_leech=True, task_ctx=task_ctx)
                            task_ctx.mark_completed()
                            log.info(f"Task {task_ctx.get_short_id()} completed successfully")
                        else:
                            task_ctx.error.set_error("Upload failed")
                            await message.reply_text(
                                f"❌ **Upload Failed** [task {task_ctx.get_short_id()}]\n\n"
                                f"File downloaded but upload to Telegram failed.\n"
                                f"File saved at: `{final_path}`",
                                quote=True
                            )
                    except Exception as upload_error:
                        log.exception(f"Task {task_ctx.get_short_id()}: Upload error")
                        task_ctx.error.set_error(str(upload_error))
                        await message.reply_text(
                            f"❌ **Upload Error** [task {task_ctx.get_short_id()}]: {str(upload_error)}\n\n"
                            f"File saved locally at: `{final_path}`",
                            quote=True
                        )
                else:
                    task_ctx.error.set_error("Download failed")
                    await message.reply_text(
                        f"❌ **Download Failed** [task {task_ctx.get_short_id()}]\n\n"
                        "Please check:\n"
                        "• URLs are valid M3U8 playlists\n"
                        "• Network connection is stable\n"
                        "• Try again with /mindvalley",
                        quote=True
                    )

            except Exception as task_error:
                log.exception(f"Task {task_ctx.get_short_id()} error")
                task_ctx.error.set_error(str(task_error))
                task_ctx.mark_completed()  # Mark as completed even on error
                await message.reply_text(
                    f"❌ **Task Error** [task {task_ctx.get_short_id()}]: {str(task_error)}",
                    quote=True
                )
            finally:
                # Clean up: remove from queue and update dashboard
                TASK_QUEUE.remove_task(task_ctx.task_id)
                await force_update_summary(client)
                log.info(f"Task {task_ctx.get_short_id()} cleanup complete")

        # NEW: Register task and launch it (non-blocking)
        TASK_QUEUE.add_task(task_ctx)
        task_ctx.async_task = asyncio.create_task(run_mindvalley_task())
        log.info(f"Task {task_ctx.get_short_id()} launched in background")

        # NEW: Update summary dashboard to show new task
        await force_update_summary(client)

        # Return immediately - task runs in background!
        log.info(f"Mindvalley handler returning - task {task_ctx.get_short_id()} continues in background")

    except Exception as e:
        log.exception("Error processing Mindvalley URLs")
        await message.reply_text(
            f"❌ **Error:** {str(e)}\n\n"
            "Please try again with /mindvalley",
            quote=True
        )

@colab_bot.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    log.info("Received /help command.")
    # Update help text to remove separate commands
    help_text = ("Send /start To Check If I am alive 🤨\n\n"
                 "**Download/Mirror Commands:**\n"
                 "  `/tupload` - Leech to Telegram\n"
                 "  `/gdupload` - Mirror to GDrive\n"
                 "  `/ytupload` - Leech YouTube-DL links\n"
                 "  `/drupload` - Leech from Colab directory\n"
                 "  `/mindvalley` - Download Mindvalley courses (M3U8)\n"
                 "Follow prompts after command (you'll be asked to select service type for /tupload & /gdupload).\n\n"
                 "**Other Commands:** `/settings`, `/setname`, `/zipaswd`, `/unzipaswd`\n\n"
                 "⚠️ **Send image for Thumbnail!**")
    await message.reply_text(help_text, quote=True, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Instructions 📖", url="https://github.com/XronTrix10/Telegram-Leecher/wiki/INSTRUCTIONS")],[InlineKeyboardButton("Channel 📣", url="https://t.me/Colab_Leecher"), InlineKeyboardButton("Group 💬", url="https://t.me/Colab_Leecher_Discuss")]]))

# Main Execution Guard
if __name__ == "__main__":
     log.info("Colab Leecher Script Starting as main...")
     if colab_bot:
          log.info("colab_bot instance found, attempting run()...")
          try: colab_bot.run()
          except Exception as run_err: log.critical(f"Bot crashed during run: {run_err}", exc_info=True)
     else: log.critical("colab_bot was not initialized successfully.")
