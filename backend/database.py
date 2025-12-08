from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base

# Docker-compose dosyasında belirlediğimiz kullanıcı adı ve şifre
# Eğer şifreni değiştirdiysen burayı da güncellemeyi unutma.
DATABASE_URL = "postgresql+asyncpg://admin:password123@localhost/safety_analysis_db"

# Veritabanı Motorunu Oluştur (Echo=True sorguları terminale yazar, debug için iyidir)
engine = create_async_engine(DATABASE_URL, echo=True)

# Oturum Oluşturucu (Session Factory)
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Tüm modellerin (tabloların) miras alacağı temel sınıf
Base = declarative_base()

# Dependency (API endpointlerinde veritabanı oturumu açıp kapatan fonksiyon)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session