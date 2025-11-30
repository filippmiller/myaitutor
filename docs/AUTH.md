# Authentication System

## Overview
The authentication system uses a hybrid approach:
- **Session Cookie (`session_id`)**: HTTP-only, secure (in prod), used for persistent sessions.
- **JWT Access Token**: Returned on login/register for future use (e.g., mobile apps or specific API calls), but currently the web app relies on the cookie.

## Data Models

### UserAccount (`user_accounts`)
- `id`: Integer PK
- `email`: Unique, indexed
- `hashed_password`: Bcrypt hash
- `full_name`: Optional string
- `is_active`: Boolean

### AuthSession (`auth_sessions`)
- `id`: UUID string PK
- `user_id`: FK to UserAccount
- `expires_at`: DateTime
- `is_revoked`: Boolean
- `user_agent`, `ip_address`: Metadata

### UserProfile
- Linked to `UserAccount` via `user_account_id` (nullable FK).
- New users get a profile automatically created.

## API Endpoints

### POST `/api/auth/register`
- Body: `{ email, password, full_name? }`
- Returns: `{ user, access_token, token_type }`
- Sets `session_id` cookie.

### POST `/api/auth/login`
- Body: `{ email, password }`
- Returns: `{ user, access_token, token_type }`
- Sets `session_id` cookie.

### POST `/api/auth/logout`
- Clears `session_id` cookie.
- Revokes session in DB.

### GET `/api/auth/me`
- Requires valid `session_id` cookie.
- Returns current user info.

## Configuration (Environment Variables)

- `AUTH_SECRET_KEY`: Secret for JWT signing.
- `ACCESS_TOKEN_EXPIRE_MINUTES`: JWT expiry (default 60).
- `SESSION_EXPIRE_HOURS`: Session cookie expiry (default 24).
- `COOKIE_SECURE`: Set to `True` in production (requires HTTPS).

## Local Development

1. Install dependencies:
   ```bash
   pip install passlib[bcrypt] python-jose[cryptography]
   ```
2. Run backend:
   ```bash
   uvicorn app.main:app --reload
   ```
3. Run frontend:
   ```bash
   cd frontend
   npm run dev
   ```
4. Open `http://localhost:5173/auth` to sign up.
