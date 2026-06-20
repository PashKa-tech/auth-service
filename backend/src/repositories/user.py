import uuid
from sqlalchemy import select, func
from src.models.user import User
from src.repositories.base import TenantScopedRepository

class UserRepository(TenantScopedRepository):
    async def create(self, email: str, password_hash: str | None, role: str = "user", is_verified: bool = False) -> User:
        user = User(
            tenant_id=self.tenant_id,
            email=email.lower().strip(),
            password_hash=password_hash,
            role=role,
            is_verified=is_verified
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id, User.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == email.lower().strip(), User.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def update(self, user: User) -> User:
        # Since it's attached to the session, we just merge or flush.
        # Enforce that tenant_id remains the same as a precaution.
        if user.tenant_id != self.tenant_id:
            raise ValueError("Cross-tenant user update attempt blocked.")
        self.db.add(user)
        await self.db.flush()
        return user

    async def list_all(self, limit: int = 50, offset: int = 0) -> list[User]:
        result = await self.db.execute(
            select(User)
            .where(User.tenant_id == self.tenant_id)
            .order_by(User.email.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

