from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..db.models import User


router = APIRouter(prefix="/users", tags=["Users"])


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str | None

    model_config = {"from_attributes": True}


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user = User(
        name=user_data.name,
        email=user_data.email,
    )
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    await db.refresh(user)
    return user