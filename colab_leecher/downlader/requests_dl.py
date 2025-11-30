#================================================
#FILE: colab_leecher/downlader/requests_dl.py
#================================================
# Telegram-Leecher/colab/downlader/requests_dl.py

async def download_multiple_files_Debrid(urls, file_names):
    # Import cancelTask locally if needed
    from colab_leecher.utility.handler import cancelTask
    global BOT, Messages # Ensure globals declared

    # Use getattr to safely access options
    cf_clearance = getattr(BOT.Options, "cf_clearance", None) # <<< FIX HERE
    if len(urls) != len(file_names):
        logger.error("Debrid URL/FN mismatch!")
        await cancelTask("Debrid URL/Filename counts mismatch.")
        return

    for idx, (url, file_name) in enumerate(zip(urls, file_names)):
        url, file_name = url.strip(), file_name.strip()
        if not file_name or not url:
            logger.warning(f"Skip Debrid [{idx+1}]: No FN/URL for {url or file_name}")
            continue
        Messages.download_name = file_name # Set for status context
        success = await download_file_Debrid(url, file_name, cf_clearance)
        if not success:
            logger.warning(f"Failed download Debrid file [{idx+1}]: {file_name}")
            # Optionally break or cancel here
            # await cancelTask(f"Stopping task due to Debrid failure: {file_name}"); break
    logger.info("Finished processing Debrid links.")


async def download_multiple_files_bitso(urls, file_names, referer_url):
    # Import cancelTask locally if needed
    from colab_leecher.utility.handler import cancelTask
    global BOT, Messages # Ensure globals declared

    # Use getattr to safely access options
    id_cookie = getattr(BOT.Options, "bitso_id_cookie", None) # <<< FIX HERE
    sess_cookie = getattr(BOT.Options, "bitso_sess_cookie", None) # <<< FIX HERE
    # referer_url is passed as argument, but if it came from options:
    # referer_url = getattr(BOT.Options, "bitso_referer", None)

    if len(urls) != len(file_names):
        logger.error("Bitso URL/FN mismatch!")
        await cancelTask("Bitso URL/Filename counts mismatch.")
        return

    for idx, (url, file_name) in enumerate(zip(urls, file_names)):
        url, file_name = url.strip(), file_name.strip()
        if not file_name or not url:
            logger.warning(f"Skip Bitso [{idx+1}]: No FN/URL for {url or file_name}")
            continue
        Messages.download_name = file_name # Set for status context
        success = await download_file_bitso(url, file_name, referer_url, id_cookie, sess_cookie)
        if not success:
             logger.warning(f"Failed download Bitso file [{idx+1}]: {file_name}")
             # Optionally break or cancel here
             # await cancelTask(f"Stopping task due to Bitso failure: {file_name}"); break
    logger.info("Finished processing Bitso links.")

async def download_multiple_files_nzbcloud(urls, file_names):
     # Import cancelTask locally if needed
     # from colab_leecher.utility.handler import cancelTask
     global BOT # Ensure global declared

     # Use getattr to safely access options
     cf_clearance = getattr(BOT.Options, "cf_clearance", None) # <<< FIX HERE
     # download_files_nzbcloud already handles multiple files
     await download_files_nzbcloud(urls, file_names, cf_clearance)
     logger.info("Finished processing NZBCloud links.")

# Ensure download_files_nzbcloud, download_file_Debrid, download_file_bitso
# internally use localized imports for helpers as corrected before.
