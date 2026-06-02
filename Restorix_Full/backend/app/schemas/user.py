import uuid
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    two_fa_enabled: bool
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.viewer
