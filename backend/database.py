import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
import os

# 1. .env dosyasını yükle
load_dotenv()

# 2. Değişkenleri al (Eğer .env yoksa varsayılan olarak ikinci parametreleri kullanır)
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password123")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "safety_analysis_db")

# 3. URL'yi oluştur
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Motoru oluştur - connection pool settings
# Supabase requires SSL connection
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Log'u kapat
    pool_size=30,
    max_overflow=10,
    pool_timeout=5,       # bağlantı beklemesini 5sn ile sınırla
    pool_pre_ping=True,   # Connection health check
    pool_recycle=1800,    # Recycle connections every 30min
    connect_args={
        "ssl": "allow",
        "timeout": 10,
        "command_timeout": 10,
        "statement_cache_size": 0,  # Supabase PgBouncer ile uyumluluk
        "server_settings": {"application_name": "work_safety_backend"}
    }
)

# Oturum Oluşturucu
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
