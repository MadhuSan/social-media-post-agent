import hashlib
import hmac
import logging
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..config import settings
from ..db.database import get_db
from ..db.models import EmailOtp, User


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


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_otp(email: str, code: str) -> str:
    key = settings.TOKEN_ENCRYPTION_KEY.encode("utf-8")
    message = f"{email}:{code}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def _send_otp_email(email: str, code: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured.",
        )
    if bool(settings.SMTP_USERNAME) != bool(settings.SMTP_PASSWORD):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured correctly.",
        )

    message = EmailMessage()
    message["Subject"] = "Your Connfas verification code"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = email
    message.set_content(
        f"Your Connfas verification code is {code}.\n\n"
        "It expires in 10 minutes. If you did not request this code, "
        "you can ignore this email."
    )

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=15,
                context=ssl.create_default_context(),
            ) as server:
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=15,
            ) as server:
                server.starttls(context=ssl.create_default_context())
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(message)
    except (OSError, smtplib.SMTPException):
        logger.exception("Failed to send email verification code")
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
        await run_in_threadpool(_send_otp_email, email, code)
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
        select(User.id)
        .where(func.lower(User.email) == email)
        .limit(1)
    )
    return VerifyOtpResponse(
        verified=True,
        existing_user=existing_user is not None,
    )
