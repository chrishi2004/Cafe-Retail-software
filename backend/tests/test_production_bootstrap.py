import pytest
from sqlalchemy import select
from app.models import BusinessProfile, Company, PaymentMode, User
from scripts.bootstrap_production import bootstrap


def test_bootstrap_creates_real_business_and_refuses_repeat(db_session_factory):
    with db_session_factory.begin() as db:
        ids = bootstrap(db, name='Real Business', email='OWNER@example.com',
                        password='unique long owner password', business_type='cafe')
    with db_session_factory() as db:
        company = db.get(Company, ids['company_id'])
        assert not company.is_demo and company.is_active
        owner = db.scalar(select(User))
        assert owner.email == 'owner@example.com' and owner.company_id is None
        assert not owner.mfa_enabled
        assert db.scalar(select(BusinessProfile)).default_tax_mode.value == 'non_gst'
        assert len(list(db.scalars(select(PaymentMode)))) == 8
        with pytest.raises(ValueError, match='already in use'):
            bootstrap(db, name='Another', email='other@example.com',
                      password='unique long owner password', business_type='retail')


def test_bootstrap_rejects_weak_password(db_session_factory):
    with db_session_factory() as db:
        with pytest.raises(ValueError, match='16 characters'):
            bootstrap(db, name='Real', email='owner@example.com', password='RetailDemo@123', business_type='retail')
        assert db.scalar(select(User)) is None
