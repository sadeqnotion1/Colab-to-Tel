# Code Quality & Naming Issues - Detailed Fix Prompt

## Problem Description
The codebase has code quality issues that can cause:
1. **Developer confusion** from inconsistent naming
2. **Maintenance nightmares** from duplicate code
3. **Misleading metrics** from incorrect calculations
4. **Integration problems** from conflicting implementations

## Root Cause Analysis

### 1. Inconsistent Naming: task_error vs error
**Files**: `task_manager.py:1076`, `handler.py:44,349`, `converters.py`, `aria2.py`, `mega.py`, `gdrive.py`
```python
# Inconsistent usage:
# handler.py:44 → _task_error = task_ctx.error  
# handler.py:349 → _task_error = task_ctx.error
# task_manager.py:136 → _task_error = task_ctx.error (in taskScheduler)
# task_manager.py:1076 → _task_error = task_ctx.task_error  # INCONSISTENT!
# converters.py (8 occurrences) → .task_error
# aria2.py (1) → .task_error
# mega.py (1) → .task_error
# gdrive.py (4) → .task_error
```

**Problem**: The canonical attribute is `.error`, but many files use `.task_error`. While `.task_error` is an alias property, this inconsistency makes code harder to understand and maintain.

### 2. Duplicate Path Definitions
**File**: `__main__.py:167-184`
```python
# Duplicate definitions:
'temp_unzip': f"{task_ctx.work_path}/temp_unzip",
'temp_unzip_path': f"{task_ctx.work_path}/temp_unzip",
```

**Problem**: Both `temp_unzip` and `temp_unzip_path` point to the same location, but the old Paths class uses `temp_unzip_path`. The `temp_unzip` key is unused — potential source of confusion if any legacy code references it.

### 3. Misleading Speed Calculation
**File**: `task_context.py:116-121`
```python
def get_speed(self) -> float:
    elapsed = time.time() - self.start_time
    current_bytes = self.get_current_bytes()
    return current_bytes / elapsed
```

**Problem**: This returns average speed since task start, not current speed. After a slow start followed by fast download, the dashboard shows a misleadingly low speed. The `last_speed` / `last_speed_bytes` fields (set by `status_bar`) would be better, but the dashboard calls `get_speed()` instead.

## Step-by-Step Solution

### Phase 1: Standardize Naming Conventions
1. **Create NamingStandard class**:
   ```python
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
                       with open(filepath, 'r') as f:
                           content = f.read()
                           
                       if '.task_error' in content:
                           inconsistencies.append(filepath)
           
           return inconsistencies
   ```

2. **Replace all .task_error with .error**:
   ```python
   # Find and replace in all files:
   # task_manager.py:1076
   _task_error = task_ctx.error  # Changed from .task_error
   
   # converters.py (8 occurrences)
   # aria2.py (1 occurrence)
   # mega.py (1 occurrence)  
   # gdrive.py (4 occurrences)
   ```

### Phase 2: Remove Duplicate Path Definitions
1. **Standardize path names**:
   ```python
   # Old code (remove):
   'temp_unzip': f"{task_ctx.work_path}/temp_unzip",
   'temp_unzip_path': f"{task_ctx.work_path}/temp_unzip",
   
   # New code (keep only one):
   'temp_unzip_path': f"{task_ctx.work_path}/temp_unzip",
   ```

2. **Add path validation**:
   ```python
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
               # ... other paths
           }
           
           # Check for duplicates
           path_values = list(paths.values())
           if len(path_values) != len(set(path_values)):
               log.error("Duplicate path values detected")
           
           return paths
   ```

### Phase 3: Fix Speed Calculation
1. **Implement dual speed calculation**:
   ```python
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
               return 0
           return sum(self._speed_samples) / len(self._speed_samples)
       
       def get_average_speed(self):
           """Get average speed since start"""
           return self._average_speed
   ```

2. **Update TaskTransfer class**:
   ```python
   class TaskTransfer:
       def __init__(self):
           self._speed_calculator = SpeedCalculator()
           # ... other init ...
       
       def update_progress(self, bytes_done, bytes_total=None):
           self._speed_calculator.update(bytes_done)
           # ... other updates ...
       
       def get_speed(self):
           """Get current speed (instantaneous)"""
           return self._speed_calculator.get_instant_speed()
       
       def get_average_speed(self):
           """Get average speed since start"""
           return self._speed_calculator.get_average_speed()
   ```

## Specific Code Changes Needed

### 1. Replace .task_error with .error
```bash
# Find all occurrences:
grep -r "\.task_error" --include="*.py" .

# Replace with:
sed -i 's/\.task_error/.error/g' *.py
```

### 2. Remove Duplicate Path
```python
# In __main__.py, remove line 167:
# 'temp_unzip': f"{task_ctx.work_path}/temp_unzip",
```

### 3. Update Speed Display
```python
# Old code in dashboard:
speed = task_ctx.transfer.get_speed()

# New code:
speed = task_ctx.transfer.get_speed()  # Now returns instantaneous
# Or for average:
average_speed = task_ctx.transfer.get_average_speed()
```

## Testing Considerations

### Unit Tests
1. Test NamingStandard auditing
2. Test PathManager validation
3. Test SpeedCalculator accuracy
4. Test backward compatibility

### Integration Tests
1. Test error handling with new naming
2. Test path operations with removed duplicates
3. Test speed display in dashboard
4. Test performance impact

### Code Quality Tests
1. Run linting tools
2. Check naming consistency
3. Verify no broken references
4. Test documentation updates

## Files to Modify
1. **Create**: `code_quality_utils.py` (naming standards, path validation)
2. **Modify**: `task_manager.py` (fix .task_error)
3. **Modify**: `converters.py` (fix .task_error)
4. **Modify**: `aria2.py` (fix .task_error)
5. **Modify**: `mega.py` (fix .task_error)
6. **Modify**: `gdrive.py` (fix .task_error)
7. **Modify**: `__main__.py` (remove duplicate path)
8. **Modify**: `task_context.py` (fix speed calculation)

## Expected Outcomes
1. **Consistent naming**: .error used everywhere
2. **No duplicate paths**: Single source of truth
3. **Accurate speed metrics**: Instantaneous + average
4. **Better maintainability**: Clear code conventions
5. **Easier onboarding**: Consistent patterns for new developers