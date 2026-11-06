from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_db
from ..services.sessions import resolve_session, revoke_session


router = APIRouter(prefix="/auth/session", tags=["Sessions"])


class SessionToken(BaseModel):
    token: str = Field(min_length=32, max_length=128)


class SessionResponse(BaseModel):
    user_id: UUID
    email: str | None
    social_account_id: UUID | None


@router.post("/restore", response_model=SessionResponse)
async def restore_session(
    request: SessionToken,
    db: AsyncSession = Depends(get_db),
):
    info = await resolve_session(db, request.token)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        )
    return SessionResponse(
        user_id=info.user_id,
        email=info.email,
        social_account_id=info.social_account_id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: SessionToken,
    db: AsyncSession = Depends(get_db),
):
    await revoke_session(db, request.token)
    await db.commit()
