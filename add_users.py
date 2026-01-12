"""
Add users to existing database.
Run this script to add new admin/worker users.
"""
from database import SessionLocal, init_db
from models import User, UserRole


def add_user(db, username: str, role: UserRole, api_key: str) -> tuple[str, str]:
    """
    Add a single user to the database.
    Returns (username, api_key) tuple.
    Raises ValueError if username or api_key already exists.
    """
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise ValueError(f"User '{username}' already exists")

    existing_key = db.query(User).filter(User.api_key == api_key).first()
    if existing_key:
        raise ValueError(f"API key '{api_key}' already in use")

    user = User(
        username=username,
        role=role,
        api_key=api_key,
        is_active=True,
    )
    db.add(user)
    db.commit()
    return username, api_key


def main():
    """Add users interactively or via predefined list."""
    print("=" * 50)
    print("사용자 추가 스크립트")
    print("=" * 50)

    # ============================================
    # 여기에 추가할 사용자를 정의하세요
    # 형식: username, role, api_key
    # ============================================
    new_users = [
        {"username": "admin2", "role": UserRole.ADMIN, "api_key": "data_admin2"},
        {"username": "worker3", "role": UserRole.WORKER, "api_key": "data_worker3"},
        {"username": "worker4", "role": UserRole.WORKER, "api_key": "data_worker4"},
        # 필요한 만큼 추가
    ]
    # ============================================

    init_db()
    db = SessionLocal()

    try:
        created = []
        skipped = []

        for user_data in new_users:
            username = user_data["username"]
            role = user_data["role"]
            api_key = user_data["api_key"]
            try:
                add_user(db, username, role, api_key)
                created.append((username, role.value, api_key))
            except ValueError as e:
                skipped.append(str(e))

        # 결과 출력
        if created:
            print("\n" + "=" * 50)
            print("생성된 사용자 - API 키를 저장하세요!")
            print("=" * 50)
            for username, role, api_key in created:
                print(f"\n{username} ({role}):")
                print(f"  API Key: {api_key}")
            print("\n" + "=" * 50)

        if skipped:
            print("\n건너뛴 사용자:")
            for msg in skipped:
                print(f"  - {msg}")

        # 전체 사용자 목록 출력
        print("\n현재 전체 사용자:")
        all_users = db.query(User).order_by(User.role, User.username).all()
        for user in all_users:
            status = "활성" if user.is_active else "비활성"
            print(f"  - {user.username} ({user.role.value}) [{status}]")

    finally:
        db.close()

    print("\n완료!")


if __name__ == "__main__":
    main()
