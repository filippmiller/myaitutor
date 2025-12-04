# Crash Fix - Syntax Error

**Date**: 2025-01-XX

## Problem

Railway app crashed with SyntaxError:
```
SyntaxError: name 'greeting_item_id' is used prior to nonlocal declaration
File "/app/app/api/voice_ws.py", line 419
```

## Root Cause

The variable `greeting_item_id` was being used in a condition (`greeting_item_id is None`) before Python could properly resolve the `nonlocal` declaration, even though `nonlocal` was declared at the beginning of the function.

## Fix

Changed the condition structure to first check the message type, then check if `greeting_item_id` is None:

**Before:**
```python
if item_type == "message" and item.get("role") == "user" and greeting_item_id is None:
    greeting_item_id = item_id
```

**After:**
```python
if item_type == "message" and item.get("role") == "user":
    if greeting_item_id is None:
        greeting_item_id = item_id
```

This helps Python properly resolve the variable scope before checking its value.

## Status

✅ Fixed and pushed to repository

