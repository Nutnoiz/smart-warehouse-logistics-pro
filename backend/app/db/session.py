from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from sqlalchemy import event
from fastapi import Request

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_integrity(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

@event.listens_for(Session, 'before_flush')
def attribute_audit_actor(session, flush_context, instances):
    from app.models import AuditLog
    for item in session.new:
        if isinstance(item, AuditLog) and item.user_id is None:
            item.user_id = session.info.get('user_id')

def get_db(request: Request):
    db = SessionLocal()
    db.info["user_id"] = getattr(request.state, "user_id", None)
    try:
        yield db
    finally:
        db.close()

