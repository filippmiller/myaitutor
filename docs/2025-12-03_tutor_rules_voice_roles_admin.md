# Tutor Rules, Voice, Roles, and Admin System

## Overview
This document describes the implementation of the advanced tutor system, including role-based access control (RBAC), system rules, user preferences (voice/addressing), and the admin interface.

## 1. Architecture & Roles

### Roles
The system now supports two roles:
- **Student**: Default role. Can access the learning app.
- **Admin**: Superuser role. Can access the Admin Dashboard to manage users and system rules.

The role is stored in the `user_accounts` table in the `role` column.
The admin email is configured via `ADMIN_EMAIL` (default: `filipp@ailingva.com`). When this email registers, it is automatically assigned the `admin` role.

### Database Schema
- **UserAccount**: Added `role` (varchar).
- **UserProfile**: Added `preferences` (JSON string) to store `preferred_address` and `preferred_voice`.
- **TutorSystemRule**: New table for global tutor behavior rules.
  - `rule_key`: Unique identifier.
  - `rule_text`: The instruction for the AI.
  - `enabled`: Boolean toggle.
  - `sort_order`: Order in the system prompt.

## 2. System Prompt Assembly
The `TutorService` (`app/services/tutor_service.py`) dynamically builds the system prompt for every interaction.
It combines:
1.  **Base Identity**: "You are a personal English tutor..."
2.  **System Rules**: Active rules from `TutorSystemRule` table.
3.  **Student Context**: Name, level, goals.
4.  **Preferences**: How to address the student (from `UserProfile.preferences`).
5.  **Memory**: Last lesson summary and weak words (from `UserState` and `SessionSummary`).

## 3. User Preferences & Voice
- **Addressing**: The tutor asks for the preferred form of address if not set.
- **Voice**: The user can select a preferred voice.
  - Supported internal values: `male_deep`, `male_neutral`, `female_neutral`, `female_soft`.
  - Mapped to OpenAI TTS voices: `onyx`, `echo`, `shimmer`, `nova`.
- **Extraction**: The system analyzes the conversation (`analyze_learning_exchange`) to detect if the user specified a preference, and updates the profile automatically.

## 4. Admin Interface
The Admin Dashboard (`/admin`) has been expanded with tabs:
- **Settings**: Global API keys and model selection.
- **Users**: List of registered users.
  - View details: English level, preferences.
- **System Rules**: Manage global rules.
  - Enable/Disable rules.
  - Edit rule text and order.

## 5. How to Use
1.  **Register Admin**: Sign up with `filipp@ailingva.com` (or the configured admin email). You will get Admin access.
2.  **Manage Rules**: Go to Admin -> System Rules to tweak how the tutor behaves for everyone.
3.  **Check Users**: Go to Admin -> Users to see who is learning and what their preferences are.

## 6. Technical Details
- **Database**: PostgreSQL (Supabase) via Railway.
- **Migration**: `update_db.py` handles schema updates using SQLAlchemy `text` for compatibility.
- **Frontend**: React with `AuthContext` updated to handle roles.
