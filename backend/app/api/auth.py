"""Signup, login and the current user."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.database import get_db
from backend.app.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_or_create_company(db: Session, name: str) -> models.Company:
    """Find the company by name or make a new one."""
    company = db.query(models.Company).filter(models.Company.name == name).first()
    if company:
        return company
    company = models.Company(name=name)
    db.add(company)
    db.flush()
    return company


@router.post("/signup", response_model=schemas.UserResponse)
def signup(body: schemas.UserCreate, db: Session = Depends(get_db)) -> models.User:
    """Create a user inside a company (the company is made if it is new)."""
    if db.query(models.User).filter(models.User.email == body.email).first():
        raise HTTPException(status_code=400, detail="This email is already registered")
    company = _get_or_create_company(db, body.company_name.strip())
    user = models.User(email=body.email, hashed_password=hash_password(body.password), company_id=company.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=schemas.Token)
def login(body: schemas.UserLogin, db: Session = Depends(get_db)) -> dict:
    """Check the password and return a Bearer token."""
    user = db.query(models.User).filter(models.User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    return {"access_token": create_access_token(user.email, user.id), "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)) -> models.User:
    """Return the logged-in user."""
    return current_user
