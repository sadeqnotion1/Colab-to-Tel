# AI Prompt Crafting Guide for Issue Resolution

This guide teaches AI assistants how to create detailed, actionable prompts for fixing codebase issues. Follow this structure to generate comprehensive fix prompts.

## Prompt Structure Template

Every prompt should contain these 7 sections in order:

### 1. Problem Description (What)
Clear, concise explanation of the issue. Include:
- What's broken or suboptimal
- Where it manifests (user-facing symptoms)
- Why it matters (impact on users/system)

**Example:**
```markdown
## Problem Description
The progress update system has three independent components fighting each other, causing:
- Double-edits on the same Telegram message
- Race conditions with MessageNotModified errors
- Inconsistent data models (SmartBytes list vs int)
- Stale stats shown to users
```

### 2. Root Cause Analysis (Why)
Technical explanation of why the problem occurs. Include:
- Specific files and line numbers
- Code snippets showing the problematic patterns
- Chain of events leading to the issue

**Example:**
```markdown
## Root Cause Analysis
**File**: `helper.py:1655-1902`
```python
# Three independent systems:
# 1. status_bar() - Legacy system
# 2. ProgressDispatcher - Newer system  
# 3. Dashboard updates - Parallel mode

# All three check TASK_QUEUE.has_task() independently
# All three use different throttle timers
```

**Problem**: Each system independently decides how to update, causing conflicts.
```

### 3. Step-by-Step Solution (How)
Detailed implementation approach with phases:
- Break solution into manageable phases
- Describe each phase's goal
- Provide pseudocode or code structure
- Explain design decisions

**Example:**
```markdown
## Step-by-Step Solution

### Phase 1: Create Centralized Manager
1. Create `ProgressManager` class
2. Implement single throttle mechanism
3. Provide unified API: `update_progress()`

### Phase 2: Refactor Existing Components
1. Modify `status_bar()` to use ProgressManager
2. Modify ProgressDispatcher to route through ProgressManager
3. Modify Dashboard to subscribe to events
```

### 4. Specific Code Changes (Where)
Exact files and code modifications needed:
- Before/after code snippets
- File paths with line numbers
- Clear instructions on what to change

**Example:**
```markdown
## Specific Code Changes Needed

### 1. New ProgressManager Class
```python
class ProgressManager:
    def __init__(self):
        self._throttle_interval = 2.0
        self._last_update_time = {}
```

### 2. Modify status_bar() Function
```python
# Old code (remove):
await msg.edit(...)

# New code:
await progress_manager.update_progress(...)
```
```

### 5. Testing Considerations (Verify)
How to verify the fix works:
- Unit tests to write
- Integration tests to run
- Manual testing steps
- Performance considerations

**Example:**
```markdown
## Testing Considerations

### Unit Tests
1. Test throttle mechanism with rapid updates
2. Test data consistency between formats
3. Test error handling

### Integration Tests
1. Test with multiple concurrent tasks
2. Test download → upload transition
3. Test cancel/cleanup scenarios
```

### 6. Files to Modify (List)
Complete list of files to create or modify:
- Group by action (Create/Modify)
- Include file paths
- Brief description of changes

**Example:**
```markdown
## Files to Modify
1. **Create**: `progress_manager.py` (new centralized manager)
2. **Modify**: `helper.py` (refactor status_bar)
3. **Modify**: `progress_dispatcher.py` (use ProgressManager)
4. **Modify**: `task_dashboard.py` (subscribe to ProgressManager)
```

### 7. Expected Outcomes (Results)
What improvements to expect:
- Bullet points of benefits
- Quantifiable improvements where possible
- User experience improvements

**Example:**
```markdown
## Expected Outcomes
1. **Eliminate double-edits**: Single update path
2. **Consistent data model**: SmartBytes throughout
3. **Reduced API calls**: Better throttling
4. **Cleaner code**: Remove legacy compatibility code
```

## Prompt Crafting Process

### Step 1: Analyze the Issue
1. **Read the audit/problem description thoroughly**
2. **Identify affected files** - Use grep/find to locate all relevant code
3. **Understand the code flow** - Trace how the problematic code executes
4. **Find the root cause** - Don't just fix symptoms

### Step 2: Group Related Issues
Combine issues that:
- Share the same root cause
- Affect the same components
- Can be fixed together
- Have dependencies on each other

**Example Groupings:**
- Progress/Status System Issues (multiple systems fighting)
- Dashboard Issues (navigation, display, mode switching)
- Worker/Queue Management (slot leaks, race conditions)

### Step 3: Design the Solution
1. **Choose the right pattern** (Manager, Coordinator, etc.)
2. **Define interfaces** - How components will interact
3. **Plan the refactoring** - Incremental changes, not big bang
4. **Consider backward compatibility** - During transition period

### Step 4: Write the Prompt
1. **Follow the 7-section structure** exactly
2. **Be specific** - File paths, line numbers, code snippets
3. **Provide context** - Don't assume prior knowledge
4. **Include examples** - Show before/after code

### Step 5: Review and Refine
1. **Check completeness** - Are all issues addressed?
2. **Verify accuracy** - Do file paths/line numbers match?
3. **Test clarity** - Can another AI understand this?
4. **Ensure actionability** - Can a developer implement this?

## Quality Checklist

Use this checklist to verify prompt quality:

### Problem Description
- [ ] Clear summary of what's wrong
- [ ] User-facing symptoms described
- [ ] Impact explained (why it matters)

### Root Cause Analysis  
- [ ] Specific files and line numbers included
- [ ] Code snippets showing the problem
- [ ] Technical chain of events explained

### Step-by-Step Solution
- [ ] Broken into manageable phases
- [ ] Each phase has clear goal
- [ ] Pseudocode or structure provided
- [ ] Design decisions explained

### Specific Code Changes
- [ ] Before/after code snippets
- [ ] Exact file paths with line numbers
- [ ] Clear change instructions

### Testing Considerations
- [ ] Unit tests described
- [ ] Integration tests outlined
- [ ] Manual testing steps included
- [ ] Performance considerations mentioned

### Files to Modify
- [ ] Complete list of files
- [ ] Grouped by action (Create/Modify)
- [ ] Brief description of changes

### Expected Outcomes
- [ ] Benefits listed as bullet points
- [ ] Quantifiable improvements where possible
- [ ] User experience improvements described

## Common Pitfalls to Avoid

### 1. Being Too Vague
**Bad:** "Fix the progress system"
**Good:** "Unify the three progress update systems (status_bar, ProgressDispatcher, Dashboard) into a single ProgressManager with consistent throttle mechanism"

### 2. Missing Context
**Bad:** "Change the update logic"
**Good:** "In `helper.py:1655-1902`, the status_bar() function directly edits Telegram messages without coordinating with ProgressDispatcher or Dashboard, causing double-edits"

### 3. No Code Examples
**Bad:** "Use a better pattern"
**Good:** "Replace direct message editing with: `await progress_manager.update_progress(task_id, bytes_done, bytes_total, speed)`"

### 4. Ignoring Testing
**Bad:** "Implement the fix"
**Good:** "Implement the fix, then test with: 1) 50 concurrent tasks, 2) rapid cancel/restart cycles, 3) 24-hour stability test"

### 5. Big Bang Approach
**Bad:** "Rewrite the entire system"
**Good:** "Phase 1: Create ProgressManager. Phase 2: Migrate status_bar(). Phase 3: Migrate ProgressDispatcher. Phase 4: Remove legacy code"

## Advanced Techniques

### 1. Dependency Mapping
Show how fixes depend on each other:
```
Issue 1 (Progress System) → Issue 7 (System Integration)
Issue 3 (Worker Slots) → Issue 4 (Upload Error Handling)
Issue 5 (UI Consistency) → Issue 6 (Code Quality)
```

### 2. Risk Assessment
Include risk levels for changes:
```markdown
### Risk Assessment
- **Low Risk**: Creating new ProgressManager class
- **Medium Risk**: Modifying status_bar() (backward compatibility)
- **High Risk**: Removing legacy code paths (test thoroughly)
```

### 3. Rollback Plan
Include how to revert if needed:
```markdown
### Rollback Plan
1. Keep legacy status_bar() code commented out for 2 releases
2. Add feature flag to enable/disable new system
3. Monitor error rates after deployment
```

### 4. Performance Impact
Quantify expected improvements:
```markdown
### Performance Impact
- **API Calls**: Reduce from ~3/sec to ~0.5/sec per task
- **Memory**: +10MB for ProgressManager, -20MB from removed duplicates
- **CPU**: 15% reduction in update processing
```

## Example Prompt Creation

Here's how to create a prompt from an issue description:

### Input Issue:
"Dashboard page navigation has race conditions. Navigation buttons don't update backend before rendering."

### Step-by-Step Creation:

1. **Analyze**: Found in `task_dashboard.py:292-314`. `set_dashboard_page()` and `update_summary_dashboard()` called concurrently.

2. **Group**: Combine with other dashboard issues (photo/text mode, duplicate messages).

3. **Design**: Create `DashboardStateManager` with proper locking.

4. **Write**: Follow 7-section structure with specific code examples.

5. **Review**: Ensure file paths correct, code snippets accurate.

### Output Prompt:
See `02_dashboard_navigation_display.md` for the complete example.

## Training Exercise

Practice creating a prompt for this issue:

**Issue:** "The app crashes when downloading files larger than 4GB because of integer overflow in progress calculation."

Apply the 7-section structure and use this guide to create a comprehensive prompt.

## Conclusion

Good prompts are:
- **Specific** - File paths, line numbers, code examples
- **Actionable** - Clear steps to implement
- **Complete** - Cover problem, solution, testing, outcomes
- **Organized** - Follow consistent structure

Use this guide to create prompts that enable AI assistants to understand and fix complex codebase issues effectively.