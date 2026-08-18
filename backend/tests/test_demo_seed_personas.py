from sqlalchemy.orm import Session, sessionmaker

from app.models import Branch, BusinessGroup, BusinessType, Company, UserRole
from scripts.seed_multi_venture import create_users


def test_multi_venture_demo_seed_creates_direct_cafe_personas(
    db_session_factory: sessionmaker[Session],
) -> None:
    with db_session_factory() as db:
        group = BusinessGroup(id=1, name="Demo Group", legal_name="Demo Group")
        retail = Company(
            id=1,
            business_group_id=1,
            business_type=BusinessType.RETAIL,
            slug="retail",
            code="DEMO_RETAIL",
            name="Demo Retail",
            legal_name="Demo Retail",
        )
        cafe = Company(
            id=2,
            business_group_id=1,
            business_type=BusinessType.CAFE,
            slug="cafe",
            code="DEMO_CAFE",
            name="Demo Cafe",
            legal_name="Demo Cafe",
        )
        retail_branches = [
            Branch(company_id=1, name=f"Retail {index}", city="Bengaluru")
            for index in range(1, 4)
        ]
        cafe_branch = Branch(company_id=2, name="Cafe Main", city="Bengaluru")
        db.add_all([group, retail, cafe, *retail_branches, cafe_branch])
        db.flush()

        users = create_users(db, group, retail, cafe, retail_branches, cafe_branch)
        db.commit()

        assert users["owner"].company_id is None
        assert users["cafe_admin"].company_id == cafe.id
        assert users["cafe_admin"].branch_id is None
        assert users["cafe_manager"].role == UserRole.STORE_MANAGER
        assert users["cafe_order_taker"].role == UserRole.ORDER_TAKER
        assert users["cafe_kitchen"].role == UserRole.KITCHEN
        assert users["cafe_analyst"].role == UserRole.ANALYST
        assert users["cafe_analyst"].branch_id is None
        assert {
            users["cafe_manager"].branch_id,
            users["cafe_order_taker"].branch_id,
            users["cafe_kitchen"].branch_id,
        } == {cafe_branch.id}
