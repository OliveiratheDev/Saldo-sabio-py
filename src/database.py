from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from config import DATABASE_URL
from models import Base

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def criar_tabelas():
    Base.metadata.create_all(engine)
    _run_lightweight_migrations()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _run_lightweight_migrations():
    # Para SQLite local, adiciona colunas novas sem derrubar dados.
    if not DATABASE_URL.startswith("sqlite"):
        return

    inspector = inspect(engine)
    with engine.begin() as conn:
        if "gastos" in inspector.get_table_names():
            cols = {col["name"] for col in inspector.get_columns("gastos")}
            if "sender" not in cols:
                conn.execute(text("ALTER TABLE gastos ADD COLUMN sender VARCHAR NOT NULL DEFAULT 'default'"))
            if "categoria" not in cols:
                conn.execute(text("ALTER TABLE gastos ADD COLUMN categoria VARCHAR"))
            if "classificacao_score" not in cols:
                conn.execute(text("ALTER TABLE gastos ADD COLUMN classificacao_score FLOAT"))
            if "classificacao_fonte" not in cols:
                conn.execute(text("ALTER TABLE gastos ADD COLUMN classificacao_fonte VARCHAR"))
            if "notificado" not in cols:
                conn.execute(text("ALTER TABLE gastos ADD COLUMN notificado BOOLEAN DEFAULT 0"))
        if "whatsapp_sessions" in inspector.get_table_names():
            cols = {col["name"] for col in inspector.get_columns("whatsapp_sessions")}
            if "ultimo_resumo_em" not in cols:
                conn.execute(text("ALTER TABLE whatsapp_sessions ADD COLUMN ultimo_resumo_em DATETIME"))