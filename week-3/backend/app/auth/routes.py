from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from app.auth.security import hash_password, verify_password
from app.auth.jwt import create_access_token, SECRET_KEY, ALGORITHM
from app.database import AsyncSessionLocal
from app.dependencies import get_current_user as get_authenticated_user
from app.models.user import User


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# Database session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# Register request
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


# Register
@router.post("/register")
async def register(
    user: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    email = user.email.strip().lower()
    existing_user = await db.scalar(select(User).where(User.email == email))

    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    hashed_password = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=email,
        hashed_password=hashed_password
    )

    db.add(new_user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists",
        )

    await db.refresh(new_user)

    return {
        "message": "User registered successfully",
        "id": new_user.id,
        "name": new_user.name,
        "email": new_user.email
    }


# OAuth2
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


# Login
@router.post("/login")
async def login(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == form_data.username)
    )

    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password"
        )

    access_token = create_access_token(
        data={"sub": str(user.id)}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


# Get current authenticated user
async def get_current_user(
    token: str = Depends(oauth2_scheme)
):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

        return user_id

    except JWTError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


# Protected route
@router.get("/protected")
async def protected_route(
    current_user: str = Depends(get_current_user)
):
    return {
        "message": "You are authenticated",
        "user_id": current_user
    }


@router.get("/me")
async def current_user_profile(current_user: User = Depends(get_authenticated_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
    }