from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base,sessionmaker
from app.config import settings
Base=declarative_base(); connect_args={'check_same_thread':False} if settings.database_url.startswith('sqlite') else {}
engine=create_engine(settings.database_url,connect_args=connect_args,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False)
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
def init_db():
    from app import models
    Base.metadata.create_all(engine)
