from typing import List, Optional
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
class PackageCreate(BaseModel):
    min_amount_rub: Decimal
    discount_percent: int
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class PackageUpdate(BaseModel):
    min_amount_rub: Optional[Decimal] = None
    discount_percent: Optional[int] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None

class GiftRequest(BaseModel):
    minutes: int
    reason: str

# Dependencies
def get_admin_user(current_user: UserAccount = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    return current_user

# Endpoints

@router.post("/packages", response_model=BillingPackage)
def create_package(
    data: PackageCreate,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    pkg = BillingPackage(**data.dict())
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg

@router.put("/packages/{package_id}", response_model=BillingPackage)
def update_package(
    package_id: int,
    data: PackageUpdate,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    pkg = db.get(BillingPackage, package_id)
    if not pkg:
        raise HTTPException(status_code=404, detail="Package not found")
    
    pkg_data = data.dict(exclude_unset=True)
    for key, value in pkg_data.items():
        setattr(pkg, key, value)
        
    db.add(pkg)
    db.commit()
    db.refresh(pkg)
    return pkg

@router.post("/users/{user_id}/gift")
def gift_minutes(
    user_id: int,
    data: GiftRequest,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    billing_service = BillingService(db)
    tx = billing_service.gift_minutes(user_id, data.minutes, data.reason, admin_id=admin.id)
    return {"status": "success", "minutes_added": data.minutes, "new_balance": billing_service.get_user_balance(user_id)}

@router.get("/users/{user_id}/billing")
def get_user_billing_details(
    user_id: int,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    billing_service = BillingService(db)
    balance = billing_service.get_user_balance(user_id)
    
    transactions = db.exec(
        select(WalletTransaction)
        .where(WalletTransaction.user_account_id == user_id)
        .order_by(WalletTransaction.created_at.desc())
    ).all()
    
    return {
        "user_id": user_id,
        "minutes_balance": balance,
        "transactions": transactions
    }

# Referral Management
from app.models import Referral

@router.get("/referrals")
def get_referrals(
    status: Optional[str] = None,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    query = select(Referral)
    if status:
        query = query.where(Referral.status == status)
    query = query.order_by(Referral.created_at.desc())
    return db.exec(query).all()

@router.post("/referrals/{referral_id}/block")
def block_referral(
    referral_id: int,
    admin: UserAccount = Depends(get_admin_user),
    db: Session = Depends(get_session)
):
    ref = db.get(Referral, referral_id)
    if not ref:
        raise HTTPException(status_code=404, detail="Referral not found")
    
    ref.status = "blocked"
    db.add(ref)
    db.commit()
    db.refresh(ref)
    return ref
