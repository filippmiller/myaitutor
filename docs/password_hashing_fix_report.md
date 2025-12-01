# Password Hashing Fix (2025-12-01)

## Issue
The registration failed with a `Traceback` related to `passlib` and `bcrypt`.
The error `_load_backend_mixin` suggests that `passlib` was trying to use `bcrypt` but couldn't find the underlying library.

## Root Cause
Although `passlib[bcrypt]` was in `requirements.txt`, the `bcrypt` library itself might not have been correctly installed or detected in the Docker environment. This is a common issue with `passlib`.

## Fix
I explicitly added `bcrypt` to `requirements.txt`.
This ensures that the `bcrypt` library is installed directly, which `passlib` relies on for hashing passwords.

## Next Steps
- The fix has been pushed.
- Wait for the new deployment.
- Try registering again with the same password.
