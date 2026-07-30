import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import Organization, Case, Debtor

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Seed base organization
    org = Organization(name="Test Studio")
    db.add(org)
    db.commit()

    yield db

    db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_case(db_session):
    org = db_session.query(Organization).first()
    case = Case(
        organization_id=org.id,
        code="PRAT-TEST-001",
        client_name="Mario Rossi",
        client_tax_code="RSSMRA80A01H501U",
        status="nuova",
    )
    db_session.add(case)
    db_session.flush()
    debtor = Debtor(
        case_id=case.id,
        first_name="Mario",
        last_name="Rossi",
        tax_code="RSSMRA80A01H501U",
        monthly_net_income=1800.0,
        monthly_expenses=600.0,
    )
    db_session.add(debtor)
    db_session.commit()
    db_session.refresh(case)
    return case
