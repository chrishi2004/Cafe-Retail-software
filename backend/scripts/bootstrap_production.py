"""Initialize a migrated, unused Local Hub from its trusted console."""
import argparse
import getpass
from datetime import date
from sqlalchemy import func, select, text
from app.core.config import DeploymentMode, settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (Branch, BusinessGroup, BusinessProfile, BusinessType, Company,
    FiscalPeriod, Invoice, InvoiceSequence, InvoiceSequenceType, PaymentMode,
    PaymentModeType, Sale, User, UserRole, Product, Customer, Supplier, Inventory)


def bootstrap(db, *, name, email, password, business_type):
    name, email = name.strip(), email.strip().lower()
    if not name or len(name) > 150 or '@' not in email or len(email) > 255:
        raise ValueError('A business name (1–150 characters) and owner email are required.')
    if len(password) < 16:
        raise ValueError('Use a unique password of at least 16 characters.')
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(64271001)'))
    if any(db.scalar(select(func.count()).select_from(m)) for m in (User, Invoice, Sale, Branch, Product, Customer, Supplier, Inventory)):
        raise ValueError('Database is already in use. Bootstrap never resets accounts or data.')
    if db.scalar(select(Company.id).where(Company.is_demo.is_(False), Company.code != 'HYBRID_RETAIL')):
        raise ValueError('An existing business requires manual review; refusing initialization.')
    for company in db.scalars(select(Company)):
        company.is_active = False
        company.is_demo = True
    group = BusinessGroup(name=name, legal_name=name)
    db.add(group)
    db.flush()
    company = Company(business_group_id=group.id, business_type=BusinessType(business_type),
        slug=business_type, code=f'LIVE_{group.id}', name=name, legal_name=name, is_demo=False)
    db.add(company)
    db.flush()
    branch = Branch(company_id=company.id, name='Main Branch')
    db.add(branch)
    db.flush()
    db.add(BusinessProfile(company_id=company.id, legal_name=name, email=email))
    db.add(User(business_group_id=group.id, company_id=None, branch_id=None, name='Business Owner',
        email=email, password_hash=hash_password(password), role=UserRole.SUPER_ADMIN))
    today = date.today()
    year = today.year if today.month >= 4 else today.year - 1
    fy = f'{year}-{str(year + 1)[-2:]}'
    db.add(FiscalPeriod(company_id=company.id, name=fy, start_date=date(year, 4, 1), end_date=date(year + 1, 3, 31)))
    for kind, prefix in ((InvoiceSequenceType.NON_GST_INVOICE, 'BILL-'),
        (InvoiceSequenceType.GST_INVOICE, 'GST-'), (InvoiceSequenceType.CREDIT_NOTE, 'CN-'),
        (InvoiceSequenceType.PURCHASE_BILL, 'PB-')):
        db.add(InvoiceSequence(company_id=company.id, branch_id=branch.id, invoice_type=kind,
            fiscal_year=fy, prefix=prefix))
    for index, mode in enumerate(PaymentModeType):
        db.add(PaymentMode(company_id=company.id, name=mode.value.replace('_', ' ').title(),
            mode_type=mode, display_order=index,
            requires_reference=mode not in {PaymentModeType.CASH, PaymentModeType.CREDIT}))
    db.flush()
    return {'business_group_id': group.id, 'company_id': company.id, 'branch_id': branch.id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--email', required=True)
    parser.add_argument('--business-type', choices=['retail', 'cafe'], required=True)
    args = parser.parse_args()
    if settings.deployment_mode != DeploymentMode.LOCAL_HUB:
        parser.error('Only a Local Hub may initialize operational data.')
    password = getpass.getpass('New owner password (minimum 16 characters): ')
    if password != getpass.getpass('Confirm password: '):
        parser.error('Passwords do not match.')
    try:
        with SessionLocal.begin() as db:
            ids = bootstrap(db, name=args.name, email=args.email, password=password, business_type=args.business_type)
    except ValueError as exc:
        parser.error(str(exc))
    print('Initialized:', ids)
    print('Enroll the owner using scripts.bootstrap_mfa before production login.')
    print('Starts in non-GST mode. Configure actual tax details before enabling GST.')


if __name__ == '__main__':
    main()
