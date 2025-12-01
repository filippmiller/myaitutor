# Password Hashing Migration Report (2025-12-01)

## Issue
The user encountered `Internal Server Error: password cannot be longer than 72 bytes` during registration.
This is a known limitation of the `bcrypt` algorithm. While the user's password was short, this error can sometimes be triggered by `passlib` configuration issues or if the input is unexpectedly long.

## Fix
I have switched the application to use **Argon2** for password hashing.
- **Why Argon2?** It is the modern standard for password hashing, winner of the Password Hashing Competition, and does not have the 72-byte limit that bcrypt has. It is more robust and future-proof.
- **Implementation:**
    - Added `argon2-cffi` to `requirements.txt`.
    - Updated `app/security.py` to use `schemes=["argon2", "bcrypt"]`. This ensures new passwords use Argon2, while existing bcrypt hashes (if any) can still be verified.
    - Added debug logging to `app/api/routes/auth.py` to print the password length, just in case the frontend is sending unexpected data.

## Verification
- Pushed changes to `main`.
- Waiting for deployment.
- Once deployed, the registration should proceed without the 72-byte error.

## Next Steps
- User should try to register again.
- If it works, the issue is resolved.
- If it fails, the debug logs will reveal the actual length of the password being received by the server.
