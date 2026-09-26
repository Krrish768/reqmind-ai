from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, security

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    company = db.query(models.Company).filter(models.Company.name == user.company_name).first()
    if not company:
        company = models.Company(name=user.company_name)
        db.add(company)
        db.commit()
        db.refresh(company)

    hashed_pw = security.hash_password(user.password)
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_pw,
        company_id=company.id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not security.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = security.create_access_token(data={"sub": db_user.email, "user_id": db_user.id})
    return {"access_token": token, "token_type": "bearer"}
