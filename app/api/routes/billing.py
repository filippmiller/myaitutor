from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models import UserAccount, BillingPackage, WalletTransaction, UserProfile
from app.services.auth_service import get_current_user
from app.services.billing_service import BillingService
from pydantic import BaseModel
from decimal import Decimal

router = APIRouter()

# Schemas
class BillingPackageRead(BaseModel):
    id: int
    min_amount_rub: Decimal
    discount_percent: int
    description: Optional[str]
    is_active: bool

class TransactionRead(BaseModel):
    id: int
    type: str
    amount_rub: Optional[Decimal]
    minutes_delta: int
    reason: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True

class BalanceResponse(BaseModel):
    minutes_balance: int
    transactions: List[TransactionRead]

# Endpoints

@router.get("/packages", response_model=List[BillingPackageRead])
def get_packages(
    db: Session = Depends(get_session)
):
    """List active deposit packages."""
    packages = db.exec(select(BillingPackage).where(BillingPackage.is_active == True).order_by(BillingPackage.sort_order)).all()
    return packages

@router.get("/balance", response_model=BalanceResponse)
def get_balance(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_session)
):
    """Get current user balance and recent transactions."""
    billing_service = BillingService(db)
    
    # Ensure balance is up to date (or trust cache)
    # For now, let's trust cache but maybe refresh if needed?
    # billing_service.get_user_balance(current_user.id) # Force refresh?
    
    # Get profile for cache
    profile = db.exec(select(UserProfile).where(UserProfile.user_account_id == current_user.id)).first()
    balance = profile.minutes_balance if profile else 0
    
    # Get transactions
    transactions = db.exec(
        select(WalletTransaction)
        .where(WalletTransaction.user_account_id == current_user.id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(50)
    ).all()
    
    # Convert datetime to string for Pydantic if needed, or let Pydantic handle it
    # Pydantic handles datetime, but our schema said str. Let's fix schema to datetime or rely on conversion.
    # Let's update TransactionRead to use datetime
    
    return BalanceResponse(
        minutes_balance=balance,
        transactions=transactions
    )

# Admin Endpoints (should be in admin router, but putting here for now or moving later)
# Let's put admin endpoints in app/api/admin.py or a new app/api/routes/billing_admin.py
