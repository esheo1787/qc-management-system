"""
Update existing users' API keys to simpler format.
Run this once to update old random API keys to memorable ones.
"""
from database import SessionLocal, init_db
from models import User, UserRole


def main():
    """Update API keys for existing users."""
    print("=" * 50)
    print("API 키 업데이트 스크립트")
    print("=" * 50)

    # 새 API 키 매핑 (username -> new_api_key)
    new_keys = {
        "admin": "data_admin1",
        "admin1": "data_admin1",
        "admin2": "data_admin2",
        "worker1": "data_worker1",
        "worker2": "data_worker2",
        "worker3": "data_worker3",
        "worker4": "data_worker4",
    }

    init_db()
    db = SessionLocal()

    try:
        users = db.query(User).all()
        updated = []

        for user in users:
            if user.username in new_keys:
                old_key = user.api_key
                new_key = new_keys[user.username]
                user.api_key = new_key
                updated.append((user.username, user.role.value, old_key, new_key))

        db.commit()

        if updated:
            print("\n업데이트된 사용자:")
            print("-" * 50)
            for username, role, old_key, new_key in updated:
                print(f"{username} ({role}):")
                print(f"  이전: {old_key[:16]}...")
                print(f"  새로: {new_key}")
                print()
        else:
            print("\n업데이트할 사용자가 없습니다.")

        # 전체 사용자 목록
        print("\n현재 전체 사용자 API 키:")
        print("=" * 50)
        all_users = db.query(User).order_by(User.role, User.username).all()
        for user in all_users:
            print(f"{user.username} ({user.role.value}): {user.api_key}")

    finally:
        db.close()

    print("\n완료!")


if __name__ == "__main__":
    main()
