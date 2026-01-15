"""
Pytest fixtures for QC Management System tests.
Uses fresh in-memory SQLite for each test function.

Strategy:
- Each test gets a completely fresh database
- No shared state between tests
- Simple and reliable isolation
"""
import os
import sys
import pytest
from typing import Generator

from starlette.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base, get_db
from main import app
from models import User, UserRole, Project, Part, Case, CaseStatus, Difficulty


# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite:///:memory:"


# =============================================================================
# Database Engine & Session (Function Scope - fresh for each test)
# =============================================================================

@pytest.fixture(scope="function")
def test_engine():
    """
    Create a fresh test database engine for each test.
    Tables are created fresh, ensuring complete isolation.
    """
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # Required for in-memory SQLite to share connection
    )
    # Create all tables fresh for this test
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_engine) -> Generator[Session, None, None]:
    """
    Create a session for the test.
    Uses autocommit=False for transaction control.
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )
    session = TestingSessionLocal()

    try:
        yield session
    finally:
        session.rollback()
        session.close()


# =============================================================================
# FastAPI Test Client with DB Override
# =============================================================================

@pytest.fixture(scope="function")
def client(db_session) -> Generator[TestClient, None, None]:
    """
    Create a test client with overridden database dependency.
    All API requests use the test session.
    """
    def override_get_db():
        # Yield the test session directly
        # DO NOT close here - fixture finalizer handles cleanup
        yield db_session

    # Override the get_db dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clear all overrides after test
    app.dependency_overrides.clear()


# =============================================================================
# Backward Compatibility Alias
# =============================================================================

@pytest.fixture(scope="function")
def test_db(db_session) -> Session:
    """Alias for db_session (backward compatibility)."""
    return db_session


# =============================================================================
# User Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def admin_user(db_session) -> User:
    """Create an admin user for testing."""
    user = User(
        username="test_admin",
        api_key="test_admin_key",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def worker_user(db_session) -> User:
    """Create a worker user for testing."""
    user = User(
        username="test_worker",
        api_key="test_worker_key",
        role=UserRole.WORKER,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def inactive_user(db_session) -> User:
    """Create an inactive user for testing."""
    user = User(
        username="test_inactive",
        api_key="test_inactive_key",
        role=UserRole.WORKER,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


# =============================================================================
# Project & Part Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_project(db_session) -> Project:
    """Create a test project."""
    project = Project(name="Test Project", is_active=True)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture(scope="function")
def test_part(db_session) -> Part:
    """Create a test part."""
    part = Part(name="Test Part")
    db_session.add(part)
    db_session.commit()
    db_session.refresh(part)
    return part


# =============================================================================
# Case Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def test_case(db_session, test_project, test_part) -> Case:
    """Create a test case in TODO status."""
    case = Case(
        case_uid="TEST-CASE-001",
        display_name="Test Case 1",
        original_name="test_case_folder",
        hospital="Test Hospital",
        slice_thickness_mm=1.0,
        project_id=test_project.id,
        part_id=test_part.id,
        difficulty=Difficulty.NORMAL,
        status=CaseStatus.TODO,
        revision=1,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


@pytest.fixture(scope="function")
def assigned_case(db_session, test_project, test_part, worker_user) -> Case:
    """Create a test case assigned to worker (in IN_PROGRESS status)."""
    case = Case(
        case_uid="TEST-CASE-002",
        display_name="Assigned Test Case",
        original_name="assigned_case_folder",
        hospital="Test Hospital",
        slice_thickness_mm=1.5,
        project_id=test_project.id,
        part_id=test_part.id,
        difficulty=Difficulty.NORMAL,
        status=CaseStatus.IN_PROGRESS,
        revision=1,
        assigned_user_id=worker_user.id,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


# =============================================================================
# Helper Functions for Tests
# =============================================================================

def admin_headers(admin_user: User) -> dict:
    """Get headers for admin authentication."""
    return {"X-API-Key": admin_user.api_key}


def worker_headers(worker_user: User) -> dict:
    """Get headers for worker authentication."""
    return {"X-API-Key": worker_user.api_key}
