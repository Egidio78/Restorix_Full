from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class Require2FAResponse(BaseModel):
    require_2fa: bool = True
    message: str = "2FA code required"


class TwoFAVerifyRequest(BaseModel):
    code: str


class TwoFADisableRequest(BaseModel):
    password: str
