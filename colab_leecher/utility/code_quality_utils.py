import os
import time
from colab_leecher.utility.logger import get_logger

log = get_logger("code_quality")

class NamingStandard:
    # Canonical attribute names
    CANONICAL_NAMES = {
        'error': 'error',  # Use .error everywhere
        'task_error': 'error',  # Deprecate .task_error
    }
    
    @classmethod
    def get_canonical_name(cls, attribute_name):
        return cls.CANONICAL_NAMES.get(attribute_name, attribute_name)
    
    @classmethod
    def audit_codebase(cls):
        """Find all inconsistent usages"""
        inconsistencies = []
        
        # Search for .task_error usage
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                        
                    if '.task_error' in content:
                        inconsistencies.append(filepath)
        
        return inconsistencies

class PathManager:
    def __init__(self):
        self._defined_paths = set()
    
    def define_path(self, name, path):
        if name in self._defined_paths:
            log.warning(f"Duplicate path definition: {name}")
        self._defined_paths.add(name)
        return path
    
    def validate_paths(self, task_ctx):
        """Ensure no duplicate paths"""
        paths = {
            'temp_unzip_path': f"{task_ctx.work_path}/temp_unzip",
        }
        
        # Check for duplicates
        path_values = list(paths.values())
        if len(path_values) != len(set(path_values)):
            log.error("Duplicate path values detected")
        
        return paths

class SpeedCalculator:
    def __init__(self):
        self._start_time = time.time()
        self._last_update_time = time.time()
        self._last_bytes = 0
        self._average_speed = 0
        self._instant_speed = 0
        self._speed_samples = []
    
    def update(self, current_bytes):
        now = time.time()
        elapsed_total = now - self._start_time
        elapsed_interval = now - self._last_update_time
        
        if elapsed_interval > 0:
            # Calculate instantaneous speed
            bytes_delta = current_bytes - self._last_bytes
            self._instant_speed = bytes_delta / elapsed_interval
            
            # Keep sample for smoothing
            self._speed_samples.append(self._instant_speed)
            if len(self._speed_samples) > 10:  # Keep last 10 samples
                self._speed_samples.pop(0)
        
        # Calculate average speed
        if elapsed_total > 0:
            self._average_speed = current_bytes / elapsed_total
        
        # Update for next interval
        self._last_update_time = now
        self._last_bytes = current_bytes
    
    def get_instant_speed(self):
        """Get current speed (smoothed)"""
        if not self._speed_samples:
            return 0.0
        return sum(self._speed_samples) / len(self._speed_samples)
    
    def get_average_speed(self):
        """Get average speed since start"""
        return self._average_speed
