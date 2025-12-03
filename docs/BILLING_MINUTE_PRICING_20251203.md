# Billing & Minute Accounting System (2025-12-03)

## Overview
AIlingva uses a minute-based billing system.
- **Base Rate**: 300 RUB/hour = 5 RUB/minute.
- **Currency**: Users see balance in **minutes**.
- **Storage**: All data stored in Supabase Postgres.

## Business Rules

### 1. Free Trial
- **Rule**: Every NEW user on registration gets **60 free minutes**.
- **Implementation**:
  - Creates a `wallet_transactions` row:
    - `type` = 'trial'
    - `minutes_delta` = +60
    - `amount_rub` = NULL
  - Updates `userprofile.minutes_balance` immediately.

### 2. Deposits & Packages
- **Rule**: Users buy minutes by depositing RUB.
- **Packages**:
  - 500 RUB   → 0% discount
  - 1000 RUB  → 10% discount
  - 2000 RUB  → 15% discount
  - 3000 RUB  → 20% discount
- **Formulas**:
  - `effective_rate_per_minute = 5 * (1 - discount_percent / 100.0)`
  - `minutes = floor( amount_rub / effective_rate_per_minute )`
- **Implementation**:
  - Creates `wallet_transactions` row:
    - `type` = 'deposit'
    - `amount_rub` = Amount
    - `minutes_delta` = computed minutes
    - `source` = 'deposit_package'
    - `source_ref` = billing_package.id
  - Updates `userprofile.minutes_balance`.

### 3. Usage (Voice Sessions)
- **Rule**: Minutes are deducted after each voice session.
- **Formulas**:
  - `billed_minutes = max(1, ceil(duration_seconds / 60.0))`
  - `billed_amount_rub = billed_minutes * 5` (for analytics)
- **Implementation**:
  - Creates `usage_sessions` row with `tariff_snapshot` (JSON).
  - Creates `wallet_transactions` row:
    - `type` = 'usage'
    - `minutes_delta` = -billed_minutes
  - Decreases `userprofile.minutes_balance`.

### 4. Referrals
- **Rule**: User A invites User B. Both get **60 free minutes** when B confirms.
- **Implementation**:
  - Creates `referrals` row linking A and B.
  - Creates 2 `wallet_transactions`:
    - For A: `type` = 'referral_reward', `minutes_delta` = +60
    - For B: `type` = 'referral_welcome', `minutes_delta` = +60
  - Updates `userprofile.minutes_balance` for both.

### 5. Admin Gifts
- **Rule**: Admins can manually grant minutes.
- **Implementation**:
  - Creates `wallet_transactions` row:
    - `type` = 'gift'
    - `minutes_delta` = +N
    - `reason` = Admin provided text

## Database Schema

### `billing_packages`
- `id` (PK)
- `min_amount_rub` NUMERIC(10,2)
- `discount_percent` INT
- `description` TEXT
- `is_active` BOOLEAN DEFAULT TRUE
- `sort_order` INT DEFAULT 0
- `created_at` TIMESTAMPTZ
- `updated_at` TIMESTAMPTZ

### `wallet_transactions`
- `id` (PK)
- `user_account_id` (FK)
- `type` TEXT ('deposit', 'trial', 'gift', 'usage', 'referral_reward', 'referral_welcome')
- `amount_rub` NUMERIC(10,2) NULL
- `minutes_delta` INT
- `source` TEXT NULL
- `source_ref` TEXT NULL
- `reason` TEXT NULL
- `created_at` TIMESTAMPTZ

### `usage_sessions`
- `id` (PK)
- `user_account_id` (FK)
- `started_at` TIMESTAMPTZ
- `ended_at` TIMESTAMPTZ
- `duration_sec` INT
- `billed_minutes` INT
- `billed_amount_rub` NUMERIC(10,2)
- `billing_status` TEXT ('pending', 'billed', 'free', 'failed')
- `tariff_snapshot` JSONB NULL
- `created_at` TIMESTAMPTZ

### `referrals`
- `id` (PK)
- `referrer_user_id` (FK)
- `referred_user_id` (FK)
- `referral_code` TEXT
- `status` TEXT ('pending', 'rewarded', 'blocked')
- `reward_minutes_for_referrer` INT DEFAULT 60
- `reward_minutes_for_referred` INT DEFAULT 60
- `created_at` TIMESTAMPTZ
- `rewarded_at` TIMESTAMPTZ NULL

### `userprofile` (Updated)
- `minutes_balance` INT NOT NULL DEFAULT 0 (Cache)

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

## Delta from v1 → v2
- **Formulas**: Confirmed `floor` for deposits and `ceil` for usage.
- **Schema**: Added `tariff_snapshot` to `usage_sessions`. Added `minutes_balance` to `userprofile` (fixed missing column).
- **Referrals**: Confirmed flow A->B with dual rewards.
- **Verification**: Added comprehensive verification script `verify_billing_phase2.py`.

## Verification Log (2025-12-03)
- **Scenario A (Registration)**: Verified. New user gets 60 min trial.
- **Scenario B (Deposits)**: Verified. Deposit 1000 RUB -> 222 mins (10% discount).
- **Scenario C (Usage)**: Verified. 8 min session -> -8 mins. `tariff_snapshot` stored as JSONB.
- **Scenario D (Gift)**: Verified. Admin gift +10 mins works.
- **Scenario E (Referrals)**: Verified. Referrer +60, Referred +60.
- **Schema**: `usage_sessions.tariff_snapshot` migrated to `JSONB`. `userprofile.minutes_balance` confirmed active.
