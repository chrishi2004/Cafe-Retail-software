"""Seed the P3 Cafe staff roles after the multi-venture demo seed."""

from __future__ import annotations

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Branch, BusinessType, Company, User, UserRole

PASSWORD = "RetailDemo@123"

USERS = [
    ("Cafe Partner Admin", "cafe.partner@hybridretail.test", UserRole.ADMIN, False),
    ("Cafe Manager", "cafe.manager@hybridretail.test", UserRole.STORE_MANAGER, True),
    ("Cafe Order Taker", "cafe.orders@hybridretail.test", UserRole.ORDER_TAKER, True),
    ("Cafe Kitchen", "cafe.kitchen@hybridretail.test", UserRole.KITCHEN, True),
    ("Cafe Analyst", "cafe.analyst@hybridretail.test", UserRole.ANALYST, False),
]


def seed_cafe_users() -> int:
    with SessionLocal() as db:
        cafe = db.scalar(
            select(Company).where(
                Company.business_type == BusinessType.CAFE,
                Company.is_active.is_(True),
            )
        )
        if cafe is None:
            raise RuntimeError("Cafe venture does not exist. Run scripts.seed_multi_venture first.")
        branch = db.scalar(
            select(Branch).where(
                Branch.company_id == cafe.id,
                Branch.is_active.is_(True),
            ).order_by(Branch.id)
        )
        if branch is None:
            raise RuntimeError("Cafe branch does not exist.")

        password_hash = hash_password(PASSWORD)
        count = 0
        for name, email, role, needs_branch in USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    business_group_id=cafe.business_group_id,
                    company_id=cafe.id,
                    branch_id=branch.id if needs_branch else None,
                    name=name,
                    email=email,
                    password_hash=password_hash,
                    role=role,
                    token_version=1,
                    is_active=True,
                )
                db.add(user)
            else:
                user.business_group_id = cafe.business_group_id
                user.company_id = cafe.id
                user.branch_id = branch.id if needs_branch else None
                user.role = role
                user.is_active = True
                user.token_version += 1
            count += 1
        db.commit()
        return count


if __name__ == "__main__":
    print(f"Cafe users seeded: {seed_cafe_users()}")
