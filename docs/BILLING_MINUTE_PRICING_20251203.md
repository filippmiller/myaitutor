# Billing & Minute Accounting System (2025-12-03)

## Overview
AIlingva uses a minute-based billing system.
- **Base Rate**: 300 RUB/hour = 5 RUB/minute.
- **Currency**: Users see balance in **minutes**.
- **Storage**: All data stored in Supabase Postgres.

## Business Rules
1. **Free Trial**: New users get **60 free minutes** upon registration.
2. **Deposits**: Users buy minutes by depositing RUB.
   - Packages define minimum amount and discount %.
   - Formula: `Minutes = Amount / (5 * (1 - Discount%))`
3. **Usage**: Minutes are deducted after each voice session.
   - Duration rounded up to the next minute (minimum 1 min).
4. **Referrals**:
   - User A invites User B.
   - Both get **60 free minutes** when B signs up/confirms.
5. **Admin Gifts**: Admins can manually add free minutes.

## Database Schema

### New Tables
- **`billing_packages`**: Deposit options (min_amount, discount).
- **`wallet_transactions`**: Ledger of all balance changes.
  - Types: `deposit`, `trial`, `gift`, `usage`, `referral_reward`, `referral_welcome`.
- **`usage_sessions`**: Log of voice sessions (duration, cost).
- **`referrals`**: Links referrer and referred user.

### Updated Tables
- **`userprofile`**: Added `minutes_balance` (cache).

## API Endpoints

### User
- `GET /api/billing/balance`: Get current balance and history.
- `GET /api/billing/packages`: Get available deposit packages.

### Admin
- `POST /api/admin/billing/packages`: Create package.
- `PUT /api/admin/billing/packages/{id}`: Update package.
- `GET /api/admin/billing/users/{id}/billing`: View user history.
- `POST /api/admin/billing/users/{id}/gift`: Give free minutes.
- `GET /api/admin/billing/referrals`: View referral history.
- `POST /api/admin/billing/referrals/{id}/block`: Block fraud referral.

## Technical Notes
- **Migrations**: Managed by Alembic. Run `railway run alembic upgrade head` to apply.
- **Connection**: Uses `DATABASE_URL` from Railway environment.
- **Services**:
  - `BillingService`: Balance, deposits, gifts.
  - `UsageService`: Session recording, charging.
  - `ReferralService`: Referral logic.
