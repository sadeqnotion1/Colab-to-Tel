# Colab Telegram Leecher Issue Prompts

This directory contains detailed fix prompts for each group of issues identified in the codebase audit. Each prompt provides:

1. **Problem Description**: Clear explanation of the issue
2. **Root Cause Analysis**: Why the problem occurs
3. **Step-by-Step Solution**: Detailed implementation approach
4. **Specific Code Changes**: Exact files and code modifications needed
5. **Testing Considerations**: How to verify the fixes work
6. **Expected Outcomes**: What improvements to expect

## Issue Groups

### 1. Progress System Unification (`01_progress_system_unification.md`)
**Critical**: Three independent progress update systems fighting each other
- Legacy status_bar() vs ProgressDispatcher vs Dashboard
- Different throttle timers and data models
- Double-edits, race conditions, stale stats

### 2. Dashboard Navigation & Display (`02_dashboard_navigation_display.md`)
**High**: Dashboard navigation and display issues
- Race conditions in page navigation
- Photo/text mode oscillation causing message spam
- Duplicate messages from non-atomic operations

### 3. Worker Slot & Queue Management (`03_worker_queue_management.md`)
**Critical**: Worker slot leaks and queue race conditions
- Unbalanced acquire/release on exceptions
- Unsafe concurrent queue operations
- Double task removal in cancel_all_tasks

### 4. Upload Error Handling (`04_upload_error_handling.md`)
**High**: Upload error handling issues
- Indefinite blocking waiting for user decisions
- Worker slot leaks on timeout
- Missing task context in error keyboards

### 5. UI Consistency & Safety (`05_ui_consistency_safety.md`)
**Medium**: UI inconsistencies and safety issues
- Three different cancel button implementations
- Null pointer exceptions in message editing
- Silent failures in size parsing

### 6. Code Quality & Naming (`06_code_quality_naming.md`)
**Medium**: Code quality and naming issues
- Inconsistent naming (.task_error vs .error)
- Duplicate path definitions
- Misleading speed calculations

### 7. Critical System Integration (`07_critical_system_integration.md`)
**Critical**: System integration issues
- Components fighting each other
- Double task removal causing queue corruption
- Fragile worker slot management

### 8. NZB Download Pipeline (`08_nzb_download_pipeline.md`)
**Critical**: NZB (Usenet) download pipeline is broken
- Binary data corruption from destroyed line framing
- Blocking nntplib I/O freezes entire bot event loop
- SABnzbdDownloader ignores task context for status updates
- NZB URL filenames broken by query parameters

## Implementation Priority

1. **Phase 1 (Critical)**: Issues 1, 3, 7, 8 - System stability & broken downloaders
2. **Phase 2 (High)**: Issues 2, 4 - User experience  
3. **Phase 3 (Medium)**: Issues 5, 6 - Code quality

## How to Use These Prompts

1. **For AI Assistants**: Each prompt is self-contained with all context needed
2. **For Developers**: Follow the step-by-step solutions
3. **For Code Review**: Use testing considerations to verify fixes

## Files Structure

```
Issues/
├── mimo.txt                           # Original audit
├── README.md                         # This file
├── 01_progress_system_unification.md # Critical progress issues
├── 02_dashboard_navigation_display.md # Dashboard issues
├── 03_worker_queue_management.md     # Worker/queue issues
├── 04_upload_error_handling.md       # Error handling issues
├── 05_ui_consistency_safety.md       # UI consistency issues
├── 06_code_quality_naming.md         # Code quality issues
├── 07_critical_system_integration.md # System integration issues
└── 08_nzb_download_pipeline.md       # NZB/Usenet download pipeline issues
```

## Next Steps

1. Review each prompt file for understanding
2. Prioritize fixes based on severity
3. Implement changes following the solutions
4. Test using the provided test considerations
5. Monitor for regressions after deployment