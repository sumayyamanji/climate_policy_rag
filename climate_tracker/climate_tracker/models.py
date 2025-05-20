"""
SQLAlchemy models for the climate policy extractor.
"""
import zoneinfo
from datetime import datetime, date

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Float, Text, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB 
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from pgvector.sqlalchemy import Vector  # Add this import


from .my_logging import get_logger
from .utils import now_london_time

Base = declarative_base()
logger = get_logger(__name__)

class CountryModel(Base):
    """Represents full-country structured text + embedding."""
    __tablename__ = 'countries'

    doc_id = Column(String, primary_key=True)
    country = Column(String)
    language = Column(String)
    text = Column(Text)
    url = Column(String)
    embedding = Column(Vector(1024))  # ← Make sure this matches your DB
    created_at = Column(DateTime(timezone=True), default=now_london_time)

    def __repr__(self):
        return f"<CountryModel(doc_id={self.doc_id}, country={self.country})>"
        
def get_db_session(database_url):
    """Create database session."""
    logger.debug(f"Creating database session for {database_url}")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def init_db(database_url):
    """Initialize database tables."""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine) 
