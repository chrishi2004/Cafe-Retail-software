from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.security import hash_password
from app.models import Branch, User, UserRole
from tests.multi_venture_fixtures import TEST_PASSWORD, seed_two_ventures


def seed_p5_test_data(factory: sessionmaker[Session]) -> dict[str, int]:
    ids = seed_two_ventures(factory)
    with factory() as db:
        second_branch = Branch(company_id=2, name="Cafe Annex", city="Bengaluru", is_active=True)
        db.add(second_branch)
        db.flush()

        users = [
            User(
                business_group_id=1,
                company_id=2,
                branch_id=ids["cafe_branch"],
                name="Cafe Manager",
                email="cafe.manager@example.test",
                password_hash=hash_password(TEST_PASSWORD),
                role=UserRole.STORE_MANAGER,
            ),
            User(
                business_group_id=1,
                company_id=2,
                branch_id=ids["cafe_branch"],
                name="Cafe Order Taker",
                email="cafe.orders@example.test",
                password_hash=hash_password(TEST_PASSWORD),
                role=UserRole.ORDER_TAKER,
            ),
            User(
                business_group_id=1,
                company_id=2,
                branch_id=ids["cafe_branch"],
                name="Cafe Kitchen",
                email="cafe.kitchen@example.test",
                password_hash=hash_password(TEST_PASSWORD),
                role=UserRole.KITCHEN,
            ),
            User(
                business_group_id=1,
                company_id=2,
                branch_id=None,
                name="Cafe Analyst",
                email="cafe.analyst@example.test",
                password_hash=hash_password(TEST_PASSWORD),
                role=UserRole.ANALYST,
            ),
        ]
        db.add_all(users)
        db.commit()
        ids.update(
            {
                "cafe_second_branch": second_branch.id,
                "cafe_manager": users[0].id,
                "cafe_order_taker": users[1].id,
                "cafe_kitchen": users[2].id,
                "cafe_analyst": users[3].id,
            }
        )
    return ids
