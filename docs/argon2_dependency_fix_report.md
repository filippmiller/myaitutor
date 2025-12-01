# Argon2 Dependency Fix (2025-12-01)

## Issue
The user received `Internal Server Error: argon2: no backends available`.
This happened because the `argon2-cffi` dependency was missing from `requirements.txt`.

## Root Cause
I attempted to add `argon2-cffi` in a previous step, but the tool call failed (likely due to a merge conflict or file state issue) and I missed the error message. As a result, the code was updated to use Argon2, but the library was never installed.

## Fix
I have successfully added `argon2-cffi` to `requirements.txt` and verified the file content.
The `requirements.txt` now correctly includes:
```
bcrypt
argon2-cffi
```

## Next Steps
- The fix has been pushed.
- Railway is rebuilding the image.
- Once deployed, the registration should work correctly with Argon2 hashing.
