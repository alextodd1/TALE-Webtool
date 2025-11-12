from sqlalchemy import Column, Integer, String, DateTime, Index
from sqlalchemy.sql import func
from app.database import Base
import secrets


def generate_session_id() -> str:
    """Generate a unique 12-character session ID"""
    return secrets.token_urlsafe(9)[:12]


class SearchSession(Base):
    """Stores search metadata and status"""

    __tablename__ = "search_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(12), unique=True, index=True, default=generate_session_id)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed
    sequence_length = Column(Integer)
    total_pairs = Column(Integer, default=0)
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_status_created", "status", "created_at"),
        Index("idx_created_at", "created_at"),
    )


class TALEPair(Base):
    """Stores individual TALE pair results"""

    __tablename__ = "tale_pairs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(12), index=True, nullable=False)

    # Sense strand (forward)
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    rvd = Column(String(60), nullable=False)

    # Antisense strand (reverse complement)
    comp_start = Column(Integer, nullable=False)
    comp_end = Column(Integer, nullable=False)
    comp_rvd = Column(String(60), nullable=False)

    # Pair properties
    spacer_length = Column(Integer, nullable=False)
    tale_length = Column(Integer, nullable=False)
    g_code = Column(String(2), nullable=False)  # NH or NN

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # Composite index for session queries with pagination
        Index("idx_session_created", "session_id", "created_at"),
        # Indexes for position-based filtering
        Index("idx_start_end", "start", "end"),
        Index("idx_comp_start_end", "comp_start", "comp_end"),
        # Index for spacer length filtering
        Index("idx_spacer_length", "spacer_length"),
    )
