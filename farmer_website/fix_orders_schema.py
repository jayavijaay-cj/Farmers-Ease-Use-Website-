from config import Config
from sqlalchemy import create_engine, text

engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
with engine.connect() as conn:
    conn.execute(text("ALTER TABLE orders ADD COLUMN transport_status VARCHAR(50) NOT NULL DEFAULT 'Pending'"))
    conn.execute(text("ALTER TABLE orders ADD COLUMN transport_notes VARCHAR(255) NULL"))
    conn.commit()
print('Schema update applied')
