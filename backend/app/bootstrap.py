"""Create an initial administrator without demo operational data."""
from sqlalchemy import select
from app.models import User
from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import hash_password


def bootstrap():
    with SessionLocal() as db:
        if not db.scalar(select(User.id).where(User.role == 'ADMIN', User.is_active.is_(True))):
            db.add(User(username=settings.bootstrap_username, password_hash=hash_password(settings.bootstrap_password), role='ADMIN'))
            db.commit()


if __name__ == '__main__':
    bootstrap()
