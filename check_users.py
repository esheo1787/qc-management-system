"""Check current users and their API keys."""
from database import SessionLocal, init_db
from models import User

init_db()
db = SessionLocal()

print("현재 사용자 목록:")
print("=" * 60)
users = db.query(User).all()
for u in users:
    print(f"{u.username} ({u.role.value}): {u.api_key}")
db.close()
