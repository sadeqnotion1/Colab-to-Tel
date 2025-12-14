#================================================
#FILE: colab_leecher/downlader/nzb.py
#================================================
# NZB (Usenet) Downloader for Telegram Leecher Bot
# Supports multiple Usenet providers, parallel downloads, and progress tracking

import os
import re
import time
import logging
import nntplib
import asyncio
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple, Optional
from pyrogram.types import Message

# Import bot globals
from ..utility.variables import BOT, Paths, MSG
from ..utility.helper import status_bar, getTime, sizeUnit
from ..utility.task_context import TaskContext

log = logging.getLogger(__name__)


class NZBDownloader:
    """
    NZB (Usenet) downloader with multi-provider support
    Follows MindvalleyDownloader pattern for consistency
    """

    def __init__(self, client, message: Message, task_ctx: TaskContext = None):
        """
        Initialize NZB downloader

        Args:
            client: Pyrogram client instance
            message: Telegram message object
            task_ctx: Optional task context for multi-task support
        """
        self.client = client
        self.message = message
        self.task_ctx = task_ctx

        # Download directory (task-specific or global)
        if task_ctx:
            self.download_dir = task_ctx.down_path
            log.info(f"Using task-specific download dir: {self.download_dir}")
        else:
            self.download_dir = Paths.down_path
            log.info(f"Using global download dir: {self.download_dir}")

        # Ensure download directory exists
        os.makedirs(self.download_dir, exist_ok=True)

        # Progress tracking variables (following Mindvalley pattern)
        self.download_start_time = 0
        self.current_percentage = 0.0
        self.current_file = ""
        self.total_articles = 0
        self.downloaded_articles = 0
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.last_update_time = 0

        # Missing/corrupted segments tracking
        self.missing_segments = []
        self.corrupted_segments = []
        self.fallback_recoveries = 0  # Articles recovered from alternate providers
        self.consecutive_missing = 0  # Track consecutive missing articles
        self.fallback_enabled = True  # Enable/disable fallback based on success rate

        # NNTP connection pool (supporting multiple providers)
        self.nntp_connections = []
        self.connection_providers = {}  # Maps connection -> provider name for fallback
        self.max_connections = 8  # Total connections across all providers

        # Get ALL provider configurations for multi-provider support
        self.provider_configs = self.get_all_providers()
        if self.provider_configs:
            total_connections = sum(p['connections'] for p in self.provider_configs)
            provider_names = ', '.join(p['name'] for p in self.provider_configs)
            log.info(f"Using {len(self.provider_configs)} provider(s): {provider_names} with {total_connections} total connections")
            self.max_connections = total_connections
        else:
            log.warning("No Usenet providers configured")

    def get_all_providers(self) -> list:
        """
        Get ALL configured Usenet providers for multi-provider support

        Returns:
            List of dicts, each containing provider config with 'name' field added
            Empty list if no providers configured
        """
        if not BOT.Setting.nzb_providers:
            return []

        providers = []
        for name, config in BOT.Setting.nzb_providers.items():
            if config.get('host'):  # Only include providers with host configured
                provider_with_name = config.copy()
                provider_with_name['name'] = name
                providers.append(provider_with_name)
                log.debug(f"Loaded provider '{name}': {config.get('host', 'N/A')}")

        return providers

    def get_active_provider(self) -> Dict:
        """
        Get configuration for currently active Usenet provider (legacy method)

        Returns:
            Dict with provider config (host, port, username, password, ssl, connections)
            Empty dict if no provider configured
        """
        provider_name = BOT.Setting.nzb_active_provider
        if not provider_name or not BOT.Setting.nzb_providers:
            return {}

        provider = BOT.Setting.nzb_providers.get(provider_name, {})
        log.debug(f"Active provider '{provider_name}': {provider.get('host', 'N/A')}")
        return provider

    def parse_nzb(self, nzb_path: str) -> Dict:
        """
        Parse NZB XML file and extract file/segment metadata

        Args:
            nzb_path: Path to .nzb file

        Returns:
            Dict with structure:
            {
                'files': [
                    {
                        'filename': str,
                        'size': int (bytes, if available),
                        'segments': [
                            {'message_id': str, 'bytes': int, 'number': int}
                        ]
                    }
                ]
            }
        """
        log.info(f"Parsing NZB file: {nzb_path}")

        try:
            tree = ET.parse(nzb_path)
            root = tree.getroot()

            # Handle namespace (NZB files use xmlns)
            namespace = {'nzb': 'http://www.newzbin.com/DTD/2003/nzb'}

            files = []
            total_segments = 0

            # Iterate through <file> elements
            for file_elem in root.findall('nzb:file', namespace):
                file_info = {}

                # Get filename from subject attribute
                file_info['filename'] = file_elem.get('subject', 'unknown_file')

                # Clean filename (remove yEnc metadata like (1/5))
                file_info['filename'] = re.sub(r'\s*\(\d+/\d+\)', '', file_info['filename'])
                file_info['filename'] = file_info['filename'].strip()

                # Try to extract actual filename from quotes
                match = re.search(r'"([^"]+)"', file_info['filename'])
                if match:
                    file_info['filename'] = match.group(1)

                # Get file size if available
                file_info['size'] = 0

                # Extract newsgroup from <groups><group> element
                file_info['newsgroups'] = []
                groups_elem = file_elem.find('nzb:groups', namespace)
                if groups_elem is not None:
                    for group_elem in groups_elem.findall('nzb:group', namespace):
                        if group_elem.text:
                            file_info['newsgroups'].append(group_elem.text.strip())

                # Parse segments
                segments = []
                segments_elem = file_elem.find('nzb:segments', namespace)

                if segments_elem is not None:
                    for segment_elem in segments_elem.findall('nzb:segment', namespace):
                        segment = {
                            'message_id': segment_elem.text.strip(),
                            'bytes': int(segment_elem.get('bytes', 0)),
                            'number': int(segment_elem.get('number', 0))
                        }
                        segments.append(segment)
                        file_info['size'] += segment['bytes']

                # Sort segments by number
                segments.sort(key=lambda x: x['number'])
                file_info['segments'] = segments
                total_segments += len(segments)

                files.append(file_info)
                log.debug(f"  File: {file_info['filename']} ({len(segments)} segments, {sizeUnit(file_info['size'])})")

            result = {'files': files}
            log.info(f"Parsed {len(files)} file(s) with {total_segments} total segments")
            return result

        except ET.ParseError as e:
            log.error(f"Failed to parse NZB XML: {e}")
            raise ValueError(f"Invalid NZB file format: {e}")
        except Exception as e:
            log.exception(f"Error parsing NZB file: {e}")
            raise

    async def connect_nntp(self, provider_config: Dict = None) -> nntplib.NNTP:
        """
        Create NNTP connection to Usenet server
        Supports both SSL and non-SSL connections

        Args:
            provider_config: Optional provider config. If None, uses first available provider

        Returns:
            NNTP connection object (authenticated)

        Raises:
            ValueError: If provider config invalid
            nntplib.NNTPError: If connection/auth fails
        """
        # Use provided config or default to first provider
        if provider_config is None:
            if self.provider_configs:
                provider_config = self.provider_configs[0]
            else:
                raise ValueError("No Usenet provider configured. Add NZB_PROVIDERS to credentials.json")

        host = provider_config.get('host')
        port = provider_config.get('port', 563)
        username = provider_config.get('username', '')
        password = provider_config.get('password', '')
        use_ssl = provider_config.get('ssl', True)
        provider_name = provider_config.get('name', 'unknown')

        if not host:
            raise ValueError("Provider configuration missing 'host' field")

        log.debug(f"Connecting to {provider_name} ({host}:{port}, SSL: {use_ssl})")

        try:
            # Create connection (SSL or plain)
            if use_ssl:
                connection = nntplib.NNTP_SSL(host, port=port, timeout=30)
            else:
                connection = nntplib.NNTP(host, port=port, timeout=30)

            # Authenticate if credentials provided
            if username and password:
                log.debug(f"Authenticating as: {username}")
                connection.login(username, password)
                log.info(f"NNTP authentication successful ({provider_name})")
            else:
                log.info(f"Connected to NNTP server ({provider_name}, no authentication)")

            # Don't select a newsgroup - modern servers support fetching articles by Message-ID
            # without group selection. If needed, the download_article method will handle it.
            log.debug(f"NNTP connection ready ({provider_name})")

            return connection

        except nntplib.NNTPPermanentError as e:
            error_code = str(e)
            if '481' in error_code or '482' in error_code:
                log.error(f"Authentication failed: {e}")
                raise ValueError(f"Usenet authentication failed. Check username/password in credentials.json")
            else:
                log.error(f"NNTP permanent error: {e}")
                raise
        except nntplib.NNTPTemporaryError as e:
            log.error(f"NNTP temporary error: {e}")
            raise
        except Exception as e:
            log.exception(f"Failed to connect to NNTP server: {e}")
            raise ValueError(f"Failed to connect to Usenet server: {e}")

    def download_article(self, connection: nntplib.NNTP, message_id: str, segment_number: int) -> Optional[bytes]:
        """
        Download single article from Usenet by message ID

        Args:
            connection: NNTP connection object
            message_id: Article message ID (e.g., <abc123@news.server.com>)
            segment_number: Segment number for logging

        Returns:
            Raw article data (yEnc encoded) or None if article missing
        """
        try:
            # Request article by message ID (newsgroup already selected during connection setup)
            response, info = connection.article(message_id)

            # Extract article body (skip headers)
            article_data = b'\n'.join(info.lines)

            log.debug(f"Downloaded segment {segment_number}: {len(article_data)} bytes")
            return article_data

        except nntplib.NNTPTemporaryError as e:
            error_code = str(e)
            if '430' in error_code:  # Article not found
                # Don't log here - let download_article_with_fallback handle it
                return None
            else:
                log.error(f"Temporary error downloading segment {segment_number}: {e}")
                raise
        except nntplib.NNTPPermanentError as e:
            log.error(f"Permanent error downloading segment {segment_number}: {e}")
            return None
        except Exception as e:
            log.exception(f"Unexpected error downloading segment {segment_number}: {e}")
            return None

    def download_article_with_fallback(self, connection: nntplib.NNTP, message_id: str, segment_number: int) -> Optional[bytes]:
        """
        Download article with smart provider fallback for missing articles.

        Tries the given connection first. If article is missing (430 error),
        tries other providers - but intelligently disables fallback if the NZB
        appears to be mostly expired (too many consecutive misses).

        Args:
            connection: Primary NNTP connection to try first
            message_id: Article message ID
            segment_number: Segment number for logging

        Returns:
            Raw article data or None if missing on ALL providers
        """
        # Try primary connection first
        primary_provider = self.connection_providers.get(id(connection), 'unknown')
        article_data = self.download_article(connection, message_id, segment_number)

        if article_data:
            # Reset consecutive missing counter on success
            self.consecutive_missing = 0
            return article_data

        # Article missing on primary provider
        self.consecutive_missing += 1

        # Disable fallback if too many consecutive misses (NZB is expired)
        # After 20 consecutive misses, stop trying fallback to prevent slowdown
        if self.consecutive_missing > 20:
            if self.fallback_enabled:
                log.warning(f"⚠️ Too many consecutive missing articles ({self.consecutive_missing}), disabling fallback to improve speed")
                self.fallback_enabled = False

        # Try other providers if fallback is still enabled
        if self.fallback_enabled and len(self.provider_configs) > 1:
            tried_providers = {primary_provider}

            for other_conn in self.nntp_connections:
                other_provider = self.connection_providers.get(id(other_conn), 'unknown')

                # Skip if same provider or already tried
                if other_provider in tried_providers:
                    continue

                log.info(f"Article {message_id} missing on {primary_provider}, trying {other_provider}...")
                tried_providers.add(other_provider)

                article_data = self.download_article(other_conn, message_id, segment_number)
                if article_data:
                    log.info(f"✅ Found on {other_provider}!")
                    self.fallback_recoveries += 1
                    self.consecutive_missing = 0  # Reset on successful fallback
                    return article_data

        # Article missing on all providers (or fallback disabled)
        if not self.fallback_enabled:
            log.debug(f"Article {message_id} missing (segment {segment_number})")
        else:
            log.warning(f"Article {message_id} not found on ANY provider (segment {segment_number}) - likely expired")

        self.missing_segments.append(segment_number)
        return None

    def decode_yenc(self, article_data: bytes) -> Optional[bytes]:
        """
        Decode yEnc encoded article data
        Tries sabyenc first, falls back to pure Python implementation

        Args:
            article_data: Raw article data with yEnc encoding

        Returns:
            Decoded binary data or None if decoding fails
        """
        if not article_data:
            return None

        try:
            # Try sabyenc (fast C implementation)
            import sabyenc

            # sabyenc expects list of chunks
            decoded, filename, crc, crc_expected, crc_correct = sabyenc.decode_usenet_chunks([article_data], None)

            if not crc_correct:
                log.warning("yEnc CRC mismatch (data may be corrupted)")

            log.debug(f"Decoded with sabyenc: {len(decoded)} bytes")
            return decoded

        except ImportError:
            log.debug("sabyenc not available, using pure Python yEnc decoder")
            return self._decode_yenc_pure_python(article_data)
        except Exception as e:
            log.warning(f"sabyenc failed ({e}), falling back to pure Python")
            return self._decode_yenc_pure_python(article_data)

    def _decode_yenc_pure_python(self, article_data: bytes) -> Optional[bytes]:
        """
        Pure Python yEnc decoder (fallback when sabyenc unavailable)

        Args:
            article_data: Raw article data with yEnc encoding

        Returns:
            Decoded binary data or None if decoding fails
        """
        try:
            lines = article_data.split(b'\n')

            # Find ybegin and yend markers
            ybegin_found = False
            yend_found = False
            encoded_data = bytearray()

            for line in lines:
                line = line.strip()

                if line.startswith(b'=ybegin'):
                    ybegin_found = True
                    continue
                elif line.startswith(b'=ypart'):
                    continue
                elif line.startswith(b'=yend'):
                    yend_found = True
                    break

                if ybegin_found and not yend_found:
                    encoded_data.extend(line)

            if not ybegin_found:
                log.error("yEnc data missing =ybegin marker")
                return None

            # Decode yEnc (subtract 42 from each byte, handle escapes)
            decoded = bytearray()
            i = 0
            while i < len(encoded_data):
                byte = encoded_data[i]

                if byte == ord('='):  # Escape character
                    if i + 1 < len(encoded_data):
                        i += 1
                        byte = (encoded_data[i] - 64 - 42) % 256
                    else:
                        log.warning("Incomplete escape sequence at end of data")
                        break
                else:
                    byte = (byte - 42) % 256

                decoded.append(byte)
                i += 1

            log.debug(f"Decoded with pure Python: {len(decoded)} bytes")
            return bytes(decoded)

        except Exception as e:
            log.exception(f"Pure Python yEnc decode failed: {e}")
            return None

    async def assemble_file(self, segments_data: List[Tuple[int, bytes]], output_path: str) -> bool:
        """
        Assemble downloaded and decoded segments into final file

        Args:
            segments_data: List of (segment_number, decoded_data) tuples
            output_path: Path where assembled file should be saved

        Returns:
            True if successful, False otherwise
        """
        try:
            log.info(f"Assembling {len(segments_data)} segments into: {output_path}")

            # Sort segments by number
            segments_data.sort(key=lambda x: x[0])

            # Write segments to file
            with open(output_path, 'wb') as f:
                for segment_num, data in segments_data:
                    if data:
                        f.write(data)

            # Verify file was created
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                log.info(f"File assembled successfully: {sizeUnit(file_size)}")
                return True
            else:
                log.error("File assembly failed - output file not created")
                return False

        except Exception as e:
            log.exception(f"Error assembling file: {e}")
            return False

    async def update_progress_bar(
        self,
        percentage: float,
        status_text: str = "Downloading...",
        speed: str = None,
        articles_done: int = None,
        articles_total: int = None
    ):
        """
        Update progress bar using bot's status_bar system
        Follows MindvalleyDownloader pattern exactly

        Args:
            percentage: Progress percentage (0-100)
            status_text: Status message (e.g., "Downloading article 150/500")
            speed: Download speed string (e.g., "5.2 MB/s") or None
            articles_done: Number of articles downloaded (optional)
            articles_total: Total articles (optional)
        """
        try:
            # Get appropriate status message (task-specific or global)
            status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg

            if not status_msg:
                return

            # Throttle updates to prevent Telegram FLOOD_WAIT errors
            # Update only every 3 seconds, except for special cases (0%, 100%, errors)
            current_time = time.time()
            time_since_last_update = current_time - self.last_update_time
            is_special_update = percentage == 0 or percentage == 100 or "❌" in status_text

            if not is_special_update and time_since_last_update < 3:
                return  # Skip this update to avoid rate limiting

            self.last_update_time = current_time

            # Update current percentage for error reporting
            self.current_percentage = percentage

            # Calculate elapsed time
            elapsed = time.time() - self.download_start_time if self.download_start_time > 0 else 0

            # Calculate ETA
            if percentage > 0 and percentage < 100 and elapsed > 0:
                eta_seconds = (elapsed / percentage) * (100 - percentage)
                eta_str = getTime(eta_seconds)
            else:
                eta_str = "N/A"

            # Format status header
            provider_name = BOT.Setting.nzb_active_provider or "Usenet"
            status_head = (
                f"<b>📰 NZB Download ({provider_name}) »</b>\n\n"
                f"<b>📄 File » </b><code>{self.current_file}</code>\n"
            )

            # Build status text
            done_text = status_text
            if articles_done is not None and articles_total is not None:
                done_text = f"Article {articles_done}/{articles_total}"

            # Add missing segments warning if any
            if self.missing_segments:
                done_text += f" (⚠️ {len(self.missing_segments)} missing)"

            # Call standard status_bar function
            await status_bar(
                down_msg=status_head,
                speed=speed if speed else "N/A",
                percentage=percentage,
                eta=eta_str,
                done=done_text,
                total_size=sizeUnit(self.total_bytes) if self.total_bytes > 0 else "Unknown",
                engine=f"NZB (NNTP)",
                task_ctx=self.task_ctx
            )

        except Exception as e:
            log.warning(f"Failed to update progress bar: {e}")

    async def download_nzb(self, nzb_path: str) -> Tuple[bool, Optional[List[str]]]:
        """
        Complete NZB download workflow

        Args:
            nzb_path: Path to .nzb file

        Returns:
            Tuple of (success: bool, output_files: List[str] or None)
        """
        self.download_start_time = time.time()
        output_files = []

        try:
            # Step 1: Parse NZB file
            log.info("=" * 50)
            log.info("Starting NZB download workflow")
            log.info("=" * 50)

            await self.update_progress_bar(0.0, "Parsing NZB file...")
            nzb_data = self.parse_nzb(nzb_path)

            if not nzb_data['files']:
                log.error("NZB file contains no files")
                await self.update_progress_bar(0.0, "❌ NZB file is empty")
                return False, None

            # Calculate totals
            self.total_articles = sum(len(f['segments']) for f in nzb_data['files'])
            self.total_bytes = sum(f['size'] for f in nzb_data['files'])
            self.downloaded_articles = 0

            log.info(f"Total: {len(nzb_data['files'])} file(s), {self.total_articles} articles, {sizeUnit(self.total_bytes)}")

            # Step 2: Create NNTP connection pool (multi-provider support)
            await self.update_progress_bar(1.0, "Connecting to Usenet...")

            log.info(f"Creating {self.max_connections} NNTP connections across {len(self.provider_configs)} provider(s)...")
            connection_count = 0

            # Create connections for each provider
            for provider in self.provider_configs:
                provider_name = provider.get('name', 'unknown')
                num_connections = provider.get('connections', 8)

                log.info(f"Creating {num_connections} connections to {provider_name}...")
                for i in range(num_connections):
                    try:
                        conn = await self.connect_nntp(provider)
                        self.nntp_connections.append(conn)
                        self.connection_providers[id(conn)] = provider_name  # Track provider for fallback
                        connection_count += 1
                        log.debug(f"Connection {connection_count}/{self.max_connections} established ({provider_name})")
                    except Exception as e:
                        log.error(f"Failed to create connection to {provider_name}: {e}")
                        if connection_count == 0 and i == 0:  # At least one connection required
                            raise

            if not self.nntp_connections:
                raise ValueError("Failed to establish any NNTP connections")

            log.info(f"Connected with {len(self.nntp_connections)} connection(s) across {len(self.provider_configs)} provider(s)")

            # Step 3: Download all files
            for file_idx, file_info in enumerate(nzb_data['files'], 1):
                filename = file_info['filename']
                segments = file_info['segments']
                newsgroups = file_info.get('newsgroups', [])

                self.current_file = filename
                log.info(f"\nDownloading file {file_idx}/{len(nzb_data['files'])}: {filename}")
                log.info(f"  Segments: {len(segments)}, Size: {sizeUnit(file_info['size'])}")
                if newsgroups:
                    log.info(f"  Newsgroup: {newsgroups[0]}")

                # NOTE: Do NOT select newsgroup when using message IDs!
                # According to nntplib docs, article(message_id) works WITHOUT group()
                # Selecting a group can cause 412/423 errors if the article isn't in that specific group

                # Download segments
                segments_data = []

                for seg_idx, segment in enumerate(segments, 1):
                    # Rotate through connection pool
                    conn_idx = seg_idx % len(self.nntp_connections)
                    connection = self.nntp_connections[conn_idx]

                    # Download article with automatic provider fallback
                    article_data = self.download_article_with_fallback(connection, segment['message_id'], segment['number'])

                    if article_data:
                        # Decode yEnc
                        decoded_data = self.decode_yenc(article_data)

                        if decoded_data:
                            segments_data.append((segment['number'], decoded_data))
                            self.downloaded_bytes += len(decoded_data)
                        else:
                            log.warning(f"Failed to decode segment {segment['number']}")
                            self.corrupted_segments.append(segment['number'])

                    # Update progress
                    self.downloaded_articles += 1
                    percentage = (self.downloaded_articles / self.total_articles) * 100

                    # Calculate speed
                    elapsed = time.time() - self.download_start_time
                    if elapsed > 0:
                        speed_bps = self.downloaded_bytes / elapsed
                        speed_str = f"{sizeUnit(speed_bps)}/s"
                    else:
                        speed_str = "N/A"

                    # Update progress bar every 2.5 seconds or on first/last segment
                    if (time.time() - self.last_update_time > 2.5) or seg_idx == 1 or seg_idx == len(segments):
                        await self.update_progress_bar(
                            percentage,
                            f"Downloading...",
                            speed=speed_str,
                            articles_done=self.downloaded_articles,
                            articles_total=self.total_articles
                        )
                        self.last_update_time = time.time()

                # Assemble file from segments
                if segments_data:
                    await self.update_progress_bar(
                        (self.downloaded_articles / self.total_articles) * 100,
                        f"Assembling file..."
                    )

                    output_path = os.path.join(self.download_dir, filename)
                    success = await self.assemble_file(segments_data, output_path)

                    if success:
                        output_files.append(output_path)
                        log.info(f"✓ File completed: {filename}")
                    else:
                        log.error(f"✗ File assembly failed: {filename}")
                else:
                    log.error(f"✗ No segments downloaded for: {filename}")

            # Step 4: Close connections
            log.info("\nClosing NNTP connections...")
            for conn in self.nntp_connections:
                try:
                    conn.quit()
                except Exception as e:
                    log.debug(f"Error closing connection: {e}")

            # Step 5: Final status
            if output_files:
                total_size = sum(os.path.getsize(f) for f in output_files)
                await self.update_progress_bar(
                    100.0,
                    f"Complete ✅ {sizeUnit(total_size)}"
                )

                # Log summary
                log.info("=" * 50)
                log.info("NZB Download Complete")
                log.info(f"Files: {len(output_files)}/{len(nzb_data['files'])}")
                log.info(f"Total Size: {sizeUnit(total_size)}")
                if self.fallback_recoveries > 0:
                    log.info(f"✅ Fallback Recoveries: {self.fallback_recoveries} articles recovered from alternate providers")
                if self.missing_segments:
                    log.warning(f"Missing segments: {len(self.missing_segments)}")
                if self.corrupted_segments:
                    log.warning(f"Corrupted segments: {len(self.corrupted_segments)}")
                log.info("=" * 50)

                return True, output_files
            else:
                await self.update_progress_bar(self.current_percentage, "❌ Download failed")
                log.error("No files were successfully downloaded")
                return False, None

        except Exception as e:
            log.exception(f"NZB download failed: {e}")
            await self.update_progress_bar(self.current_percentage, f"❌ Error: {str(e)[:50]}")

            # Close any open connections
            for conn in self.nntp_connections:
                try:
                    conn.quit()
                except:
                    pass

            return False, None
