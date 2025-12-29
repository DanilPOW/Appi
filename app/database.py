from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

engine = create_async_engine("sqlite+aiosqlite:///./tasks.db")
DBSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=AsyncSession)

async def get_db():
    db = DBSession()
    try:
        yield db
    finally:
        await db.close()