import asyncio
import time
from typing import Optional

_unified_progress = None

class UnifiedProgressSystem:
    def __init__(self):
        self._update_queue = asyncio.Queue()
        self._throttle_interval = 2.0  # seconds
        self._last_update = {}

    def reset(self):
        self._last_update.clear()
        self._update_queue = asyncio.Queue()
    
    async def update_progress(self, task_id: Optional[str], progress_data: dict):
        """Unified progress update entry point"""
        # 1. Update stats immediately if task_ctx is provided (so stats are updated in real-time)
        task_ctx = progress_data.get('task_ctx')
        if not task_ctx and task_id:
            from .task_context import TASK_QUEUE
            task_ctx = TASK_QUEUE.active_tasks.get(task_id)
            
        if task_ctx:
            transfer = task_ctx.transfer
            from .transfer_state import SmartBytes
            if not isinstance(transfer.down_bytes, SmartBytes):
                transfer.down_bytes = SmartBytes(transfer.down_bytes)
            if not isinstance(transfer.up_bytes, SmartBytes):
                transfer.up_bytes = SmartBytes(transfer.up_bytes)
                
            is_upload = progress_data.get('is_upload', False)
            bytes_done = progress_data.get('done', 0.0)
            bytes_total = progress_data.get('total', 0.0)
            
            if is_upload:
                if not transfer.up_bytes:
                    transfer.up_bytes.append(int(bytes_done))
                else:
                    transfer.up_bytes[-1] = int(bytes_done)
            else:
                if not transfer.down_bytes:
                    transfer.down_bytes.append(int(bytes_done))
                else:
                    transfer.down_bytes[-1] = int(bytes_done)
                    
            if bytes_total is not None and bytes_total > 0:
                transfer.total_size = int(bytes_total)
                
            transfer.update_progress(transfer.get_current_bytes(), transfer.total_size)
            
            # Parse and set speed
            speed = progress_data.get('speed', 'N/A')
            parsed_speed = 0.0
            if isinstance(speed, (int, float)):
                parsed_speed = float(speed)
            elif speed and speed != "N/A":
                import re
                try:
                    speed_str = str(speed).strip()
                    speed_match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z/]+)", speed_str)
                    if speed_match:
                        speed_val = float(speed_match.group(1))
                        unit = speed_match.group(2).replace('/s', '').upper().strip()
                        multiplier = 1
                        if 'G' in unit:
                            multiplier = 1024**3
                        elif 'M' in unit:
                            multiplier = 1024**2
                        elif 'K' in unit:
                            multiplier = 1024
                        parsed_speed = speed_val * multiplier
                except Exception:
                    pass
            else:
                parsed_speed = transfer.get_speed()
                
            transfer.last_speed = parsed_speed
            transfer.last_speed_bytes = parsed_speed

        self._update_queue.put_nowait({
            'task_id': task_id,
            'data': progress_data,
            'timestamp': time.monotonic()
        })
        await self._process_updates()
        
    async def _process_updates(self):
        while not self._update_queue.empty():
            update = self._update_queue.get_nowait()
            task_id = update['task_id']
            data = update['data']
            force = data.get('force', False)
            
            key = task_id if task_id is not None else "global"
            now = time.monotonic()
            
            # First update for any key always proceeds
            if key not in self._last_update:
                pass
            elif not force and (now - self._last_update[key] < self._throttle_interval):
                continue
                
            await self._apply_update(update)
            self._last_update[key] = now

    async def _apply_update(self, update):
        task_id = update['task_id']
        data = update['data']
        
        from .progress_manager import get_progress_manager
        pm = get_progress_manager()
        
        await pm.update_progress(
            task_id=task_id,
            bytes_done=data.get('done', 0.0),
            bytes_total=data.get('total', 0.0),
            speed=data.get('speed', 'N/A'),
            eta=data.get('eta', 'N/A'),
            percentage=data.get('percentage', 0.0),
            is_upload=data.get('is_upload', False),
            engine=data.get('engine', 'Unknown'),
            use_custom_text=data.get('use_custom_text', False),
            custom_text=data.get('custom_text', ''),
            force=data.get('force', False),
            task_ctx=data.get('task_ctx', None)
        )

def get_unified_progress() -> UnifiedProgressSystem:
    global _unified_progress
    if _unified_progress is None:
        _unified_progress = UnifiedProgressSystem()
    return _unified_progress
