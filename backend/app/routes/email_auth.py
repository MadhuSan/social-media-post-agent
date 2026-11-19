import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.database import get_db
from ..db.models import EmailOtp, User
from ..services.sessions import create_session


router = APIRouter(prefix="/auth/email", tags=["Email Authentication"])
logger = logging.getLogger(__name__)

OTP_LENGTH = 6
OTP_TTL = timedelta(minutes=10)
OTP_RESEND_COOLDOWN = timedelta(seconds=60)
OTP_MAX_ATTEMPTS = 5


class SendOtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class SendOtpResponse(BaseModel):
    message: str


class VerifyOtpResponse(BaseModel):
    verified: bool
    existing_user: bool
    user_id: str | None
    session_token: str | None = None


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_otp(email: str, code: str) -> str:
    key = settings.TOKEN_ENCRYPTION_KEY.encode("utf-8")
    message = f"{email}:{code}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


async def _send_otp_email(email: str, code: str) -> None:
    if not settings.RESEND_API_KEY or not settings.EMAIL_FROM_ADDRESS:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email API delivery is not configured.",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": settings.EMAIL_FROM_ADDRESS,
                    "to": [email],
                    "subject": "Your Connfas verification code",
                    "text": (
                        f"Your Connfas verification code is {code}.\n\n"
                        "It expires in 10 minutes. If you did not request this code, "
                        "you can ignore this email."
                    ),
                },
            )
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        logger.error(
            "Email API rejected verification email with HTTP %s",
            error.response.status_code,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The verification email could not be sent.",
        ) from None
    except httpx.RequestError:
        logger.exception("Email API request failed while sending verification email")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The verification email could not be sent.",
        ) from None


@router.post("/send-otp", response_model=SendOtpResponse)
async def send_email_otp(
    request: SendOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    email = _normalize_email(str(request.email))
    now = datetime.now(timezone.utc)
    otp_record = await db.get(EmailOtp, email)
    if otp_record is not None and now - otp_record.created_at < OTP_RESEND_COOLDOWN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait before requesting another verification code.",
        )

    code = f"{secrets.randbelow(10**OTP_LENGTH):0{OTP_LENGTH}d}"
    code_hash = _hash_otp(email, code)
    if otp_record is None:
        otp_record = EmailOtp(
            email=email,
            code_hash=code_hash,
            expires_at=now + OTP_TTL,
            failed_attempts=0,
            created_at=now,
        )
        db.add(otp_record)
    else:
        otp_record.code_hash = code_hash
        otp_record.expires_at = now + OTP_TTL
        otp_record.failed_attempts = 0
        otp_record.created_at = now

    await db.commit()
    try:
        await _send_otp_email(email, code)
    except HTTPException:
        await db.execute(
            delete(EmailOtp).where(
                EmailOtp.email == email,
                EmailOtp.code_hash == code_hash,
            )
        )
        await db.commit()
        raise

    return SendOtpResponse(
        message="If the address can receive email, a verification code has been sent."
    )


@router.post("/verify-otp", response_model=VerifyOtpResponse)
async def verify_email_otp(
    request: VerifyOtpRequest,
    db: AsyncSession = Depends(get_db),
):
    email = _normalize_email(str(request.email))
    result = await db.execute(
        select(EmailOtp)
        .where(EmailOtp.email == email)
        .with_for_update()
    )
    otp_record = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if otp_record is None or otp_record.expires_at <= now:
        if otp_record is not None:
            await db.delete(otp_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired.",
        )

    if otp_record.failed_attempts >= OTP_MAX_ATTEMPTS:
        await db.delete(otp_record)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect codes. Request a new verification code.",
        )

    expected_hash = _hash_otp(email, request.code)
    if not hmac.compare_digest(otp_record.code_hash, expected_hash):
        otp_record.failed_attempts += 1
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code is invalid or expired.",
        )

    await db.delete(otp_record)
    await db.commit()

    existing_user = await db.scalar(
        select(User)
        .where(func.lower(User.email) == email)
        .limit(1)
    )
    session_token = None
    if existing_user is not None:
        session_token = await create_session(db, existing_user.id)
        await db.commit()

    return VerifyOtpResponse(
        verified=True,
        existing_user=existing_user is not None,
        user_id=str(existing_user.id) if existing_user is not None else None,
        session_token=session_token,
    )
