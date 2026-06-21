from pydantic import BaseModel, EmailStr, Field

class CaptchaBase(BaseModel):
    captcha_token: str | None = None
    captcha_id: str | None = None

class UserRegisterRequest(CaptchaBase):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)

class UserLoginRequest(CaptchaBase):
    email: EmailStr
    password: str

class ForgotPasswordRequest(CaptchaBase):
    email: EmailStr

class ResetPasswordRequest(CaptchaBase):
    token: str
    new_password: str = Field(..., min_length=8, max_length=128)

class TwoFactorConfirmRequest(BaseModel):
    totp_code: str

class TwoFactorVerifyRequest(BaseModel):
    mfa_token: str
    totp_code: str

class TwoFactorDisableRequest(BaseModel):
    password: str | None = None
    totp_code: str | None = None

class OAuthTokenRequest(BaseModel):
    code: str
    code_verifier: str

class WebAuthnLoginBeginRequest(CaptchaBase):
    email: EmailStr

class WebAuthnRegisterCompleteRequest(BaseModel):
    response: dict
    name: str = "Passkey"

class WebAuthnLoginCompleteRequest(BaseModel):
    email: EmailStr
    response: dict
