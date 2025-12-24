"""
SABnzbd API Client

Wrapper for SABnzbd API to submit NZBs, monitor queue, and retrieve completed downloads.
"""

import requests
import time
import os
from typing import Optional, Dict, List, Tuple
from pathlib import Path


class SABnzbdClient:
    """Client for interacting with SABnzbd API"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8080, api_key: str = ""):
        """
        Initialize SABnzbd client

        Args:
            host: SABnzbd host
            port: SABnzbd port
            api_key: SABnzbd API key
        """
        self.host = host
        self.port = port
        self.api_key = api_key
        self.base_url = f"http://{host}:{port}/sabnzbd/api"

    def _request(self, params: Dict, files: Optional[Dict] = None) -> Dict:
        """
        Make API request to SABnzbd

        Args:
            params: Query parameters
            files: Files to upload (for NZB submission)

        Returns:
            Response data as dict
        """
        params['apikey'] = self.api_key
        params['output'] = 'json'

        try:
            if files:
                response = requests.post(self.base_url, params=params, files=files, timeout=30)
            else:
                response = requests.get(self.base_url, params=params, timeout=30)

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            raise Exception(f"SABnzbd API request failed: {e}")

    def get_version(self) -> str:
        """Get SABnzbd version"""
        result = self._request({'mode': 'version'})
        return result.get('version', 'unknown')

    def is_alive(self) -> bool:
        """Check if SABnzbd is running and accessible"""
        try:
            self.get_version()
            return True
        except:
            return False

    def add_nzb_file(self, nzb_path: str, category: str = "Default", priority: int = 0) -> Tuple[bool, str]:
        """
        Submit NZB file to SABnzbd

        Args:
            nzb_path: Path to .nzb file
            category: Download category
            priority: Priority (-2=Paused, -1=Low, 0=Normal, 1=High, 2=Force)

        Returns:
            Tuple of (success, nzo_id or error message)
        """
        if not os.path.exists(nzb_path):
            return False, f"NZB file not found: {nzb_path}"

        try:
            with open(nzb_path, 'rb') as f:
                files = {'nzbfile': f}
                params = {
                    'mode': 'addfile',
                    'cat': category,
                    'priority': str(priority)
                }

                result = self._request(params, files=files)

                if result.get('status'):
                    nzo_ids = result.get('nzo_ids', [])
                    if nzo_ids:
                        return True, nzo_ids[0]
                    else:
                        return True, "unknown"
                else:
                    error = result.get('error', 'Unknown error')
                    return False, error

        except Exception as e:
            return False, str(e)

    def add_nzb_url(self, nzb_url: str, category: str = "Default", priority: int = 0) -> Tuple[bool, str]:
        """
        Submit NZB URL to SABnzbd

        Args:
            nzb_url: URL to .nzb file
            category: Download category
            priority: Priority (-2=Paused, -1=Low, 0=Normal, 1=High, 2=Force)

        Returns:
            Tuple of (success, nzo_id or error message)
        """
        try:
            params = {
                'mode': 'addurl',
                'name': nzb_url,
                'cat': category,
                'priority': str(priority)
            }

            result = self._request(params)

            if result.get('status'):
                nzo_ids = result.get('nzo_ids', [])
                if nzo_ids:
                    return True, nzo_ids[0]
                else:
                    return True, "unknown"
            else:
                error = result.get('error', 'Unknown error')
                return False, error

        except Exception as e:
            return False, str(e)

    def get_queue(self) -> Dict:
        """
        Get current queue status

        Returns:
            Queue information including active downloads
        """
        result = self._request({'mode': 'queue'})
        return result.get('queue', {})

    def get_history(self, limit: int = 10) -> List[Dict]:
        """
        Get download history

        Args:
            limit: Maximum number of entries to retrieve

        Returns:
            List of completed downloads
        """
        result = self._request({'mode': 'history', 'limit': str(limit)})
        return result.get('history', {}).get('slots', [])

    def get_download_status(self, nzo_id: str) -> Optional[Dict]:
        """
        Get status of specific download

        Args:
            nzo_id: NZB ID from add_nzb_*

        Returns:
            Download status or None if not found
        """
        # Check queue first
        queue = self.get_queue()
        for slot in queue.get('slots', []):
            if slot.get('nzo_id') == nzo_id:
                return {
                    'status': 'downloading',
                    'name': slot.get('filename'),
                    'size': slot.get('size'),
                    'size_left': slot.get('sizeleft'),
                    'percentage': slot.get('percentage', 0),
                    'speed': slot.get('speed'),
                    'eta': slot.get('eta'),
                    'category': slot.get('cat'),
                    'priority': slot.get('priority'),
                }

        # Check history
        history = self.get_history(limit=50)
        for item in history:
            if item.get('nzo_id') == nzo_id:
                return {
                    'status': item.get('status'),  # 'Completed', 'Failed', etc.
                    'name': item.get('name'),
                    'size': item.get('size'),
                    'category': item.get('category'),
                    'download_time': item.get('download_time'),
                    'storage': item.get('storage'),  # Path to downloaded files
                    'fail_message': item.get('fail_message', ''),
                }

        return None

    def pause_download(self, nzo_id: str) -> bool:
        """Pause specific download"""
        try:
            self._request({'mode': 'queue', 'name': 'pause', 'value': nzo_id})
            return True
        except:
            return False

    def resume_download(self, nzo_id: str) -> bool:
        """Resume specific download"""
        try:
            self._request({'mode': 'queue', 'name': 'resume', 'value': nzo_id})
            return True
        except:
            return False

    def delete_download(self, nzo_id: str, delete_files: bool = False) -> bool:
        """
        Delete download from queue

        Args:
            nzo_id: NZB ID
            delete_files: Also delete downloaded files

        Returns:
            Success status
        """
        try:
            mode = 'queue'
            self._request({
                'mode': mode,
                'name': 'delete',
                'value': nzo_id,
                'del_files': '1' if delete_files else '0'
            })
            return True
        except:
            return False

    def get_queue_stats(self) -> Dict:
        """
        Get overall queue statistics

        Returns:
            Dict with queue stats (size, speed, ETA, etc.)
        """
        queue = self.get_queue()
        return {
            'active': queue.get('noofslots', 0),
            'paused': queue.get('paused', False),
            'pause_int': queue.get('pause_int', '0'),
            'speed': queue.get('speed', '0'),
            'size_left': queue.get('sizeleft', '0'),
            'size_total': queue.get('mb', '0'),
            'eta': queue.get('eta', 'unknown'),
            'time_left': queue.get('timeleft', '0:00:00'),
        }

    def wait_for_completion(self, nzo_id: str, timeout: int = 3600, check_interval: int = 5) -> Tuple[bool, str]:
        """
        Wait for download to complete

        Args:
            nzo_id: NZB ID to wait for
            timeout: Maximum wait time in seconds
            check_interval: How often to check status

        Returns:
            Tuple of (success, download_path or error_message)
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_download_status(nzo_id)

            if not status:
                return False, "Download not found in queue or history"

            if status['status'] == 'downloading':
                # Still downloading, wait
                time.sleep(check_interval)
                continue

            elif status['status'] == 'Completed':
                # Download complete
                storage = status.get('storage', '')
                return True, storage

            else:
                # Failed or other terminal state
                fail_msg = status.get('fail_message', status['status'])
                return False, f"Download failed: {fail_msg}"

        return False, f"Timeout after {timeout} seconds"


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = SABnzbdClient(api_key="your_api_key_here")

    # Check if SABnzbd is running
    if client.is_alive():
        print(f"✅ SABnzbd version: {client.get_version()}")

        # Get queue stats
        stats = client.get_queue_stats()
        print(f"Queue: {stats['active']} active, Speed: {stats['speed']}")

    else:
        print("❌ SABnzbd is not running")
