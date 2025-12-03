from typing import Optional, List, Dict
from sqlmodel import SQLModel, Field, Relationship
from pydantic import EmailStr
from datetime import datetime
import json

class AppSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True)
    openai_api_key: Optional[str] = None
    default_model: str = Field(default="gpt-4o-mini")
    # Deepgram fields removed
    # deepgram_api_key: Optional[str] = None
    # deepgram_voice_id: str = Field(default="aura-asteria-en")

class LessonSession(SQLModel, table=True):
    __tablename__ = "lesson_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_id: int = Field(foreign_key="user_accounts.id", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    status: str = Field(default="active") # active, completed, error

class LessonTurn(SQLModel, table=True):
    __tablename__ = "lesson_turns"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="lesson_sessions.id", index=True)
    speaker: str # "user" or "assistant"
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    english_level: str  # A1, A2, B1, B2, C1
    goals: Optional[str] = None
    pains: Optional[str] = None
    preferences: str = Field(default="{}") # JSON: { "preferred_address": "...", "preferred_voice": "..." }
    
    # Voice Settings
    preferred_tts_engine: str = Field(default="openai")
    preferred_stt_engine: str = Field(default="openai")
    preferred_voice_id: Optional[str] = Field(default=None)
    
    # Billing Cache
    minutes_balance: int = Field(default=0)

    
    # Relationship to UserState
    state: Optional["UserState"] = Relationship(back_populates="user")
    messages: List["SessionMessage"] = Relationship(back_populates="user")
    
    user_account_id: Optional[int] = Field(default=None, foreign_key="user_accounts.id", index=True)


class UserState(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="userprofile.id")
    
    # New field for auth linking
    user_account_id: Optional[int] = Field(default=None, foreign_key="user_accounts.id", index=True)
    
    weak_words_json: str = Field(default="[]") # Stored as JSON string
    known_words_json: str = Field(default="[]") # Stored as JSON string
    last_level_estimate: Optional[str] = None

    user: Optional[UserProfile] = Relationship(back_populates="state")

    @property
    def weak_words(self) -> List[str]:
        return json.loads(self.weak_words_json)
    
    @weak_words.setter
    def weak_words(self, value: List[str]):
        self.weak_words_json = json.dumps(value)

    @property
    def known_words(self) -> List[str]:
        return json.loads(self.known_words_json)
    
    @known_words.setter
    def known_words(self, value: List[str]):
        self.known_words_json = json.dumps(value)

    # Progress counters
    session_count: int = Field(default=0)
    total_messages: int = Field(default=0)
    last_session_at: Optional[datetime] = Field(default=None)
    xp_points: int = Field(default=0)

class SessionSummary(SQLModel, table=True):
    __tablename__ = "session_summaries"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_id: int = Field(foreign_key="user_accounts.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Short natural-language summary of what was practiced in this interaction
    summary_text: Optional[str] = None

    # JSON-encoded arrays of words/notes
    practiced_words_json: Optional[str] = None   # list[str]
    weak_words_json: Optional[str] = None        # list[str]
    grammar_notes_json: Optional[str] = None     # list[str]

class SessionMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="userprofile.id")
    
    # New field for auth linking
    user_account_id: Optional[int] = Field(default=None, foreign_key="user_accounts.id", index=True)
    
    role: str # "user" or "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: Optional[UserProfile] = Relationship(back_populates="messages")

class UserAccount(SQLModel, table=True):
    __tablename__ = "user_accounts"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    full_name: Optional[str] = Field(default=None, nullable=True)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    role: str = Field(default="student")

class TutorSystemRule(SQLModel, table=True):
    __tablename__ = "tutor_system_rules"
    id: Optional[int] = Field(default=None, primary_key=True)
    rule_key: str = Field(unique=True)
    rule_text: str
    enabled: bool = Field(default=True)
    sort_order: int = Field(default=0)

class UserAccountRead(SQLModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    role: str

class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_sessions"
    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user_accounts.id", index=True, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(nullable=False)
    is_revoked: bool = Field(default=False)
    user_agent: Optional[str] = Field(default=None, nullable=True)
    ip_address: Optional[str] = Field(default=None, nullable=True)


# --- Billing Models ---

from decimal import Decimal
from sqlalchemy import Column, Numeric

class BillingPackage(SQLModel, table=True):
    __tablename__ = "billing_packages"
    id: Optional[int] = Field(default=None, primary_key=True)
    min_amount_rub: Decimal = Field(sa_column=Column(Numeric(10, 2)))
    discount_percent: int
    description: Optional[str] = None
    is_active: bool = Field(default=True)
    sort_order: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class WalletTransaction(SQLModel, table=True):
    __tablename__ = "wallet_transactions"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_id: int = Field(foreign_key="user_accounts.id", index=True)
    type: str # deposit, trial, gift, usage, referral_reward, referral_welcome, adjustment
    amount_rub: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(10, 2)))
    minutes_delta: int
    source: Optional[str] = None
    source_ref: Optional[str] = None
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional: Relationship to UserAccount if needed
    # user: Optional["UserAccount"] = Relationship(back_populates="transactions")

class UsageSession(SQLModel, table=True):
    __tablename__ = "usage_sessions"
    id: Optional[int] = Field(default=None, primary_key=True)
    user_account_id: int = Field(foreign_key="user_accounts.id", index=True)
    started_at: datetime
    ended_at: datetime
    duration_sec: int
    billed_minutes: int
    billed_amount_rub: Decimal = Field(sa_column=Column(Numeric(10, 2)))
    billing_status: str # pending, billed, free, failed
    tariff_snapshot: Optional[str] = None # JSON string
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Referral(SQLModel, table=True):
    __tablename__ = "referrals"
    id: Optional[int] = Field(default=None, primary_key=True)
    referrer_user_id: int = Field(foreign_key="user_accounts.id", index=True)
    referred_user_id: int = Field(foreign_key="user_accounts.id", index=True)
    referral_code: str = Field(index=True)
    status: str # pending, rewarded, blocked
    reward_minutes_for_referrer: int = Field(default=60)
    reward_minutes_for_referred: int = Field(default=60)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    rewarded_at: Optional[datetime] = None

