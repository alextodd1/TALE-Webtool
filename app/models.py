"""Database models for TALE Finder"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, Text, Index
from sqlalchemy.sql import func
from app.database import Base
import secrets
import hashlib


def generate_session_id() -> str:
    """Generate a unique 12-character session ID"""
    return secrets.token_urlsafe(9)[:12]


def generate_search_hash(
    sequence: str,
    search_mode: str,
    orientation: str,
    min_tale_length: int,
    max_tale_length: int,
    min_spacer_length: int,
    max_spacer_length: int,
    g_code: str,
    skip_cpg: bool,
    skip_consecutive_at: bool,
    min_gc: int,
    search_position: int | None = None,
    search_position_range: int | None = None,
) -> str:
    """
    Generate a hash of search parameters to detect duplicate searches.
    Returns first 16 characters of SHA256 hash.
    """
    # Normalize sequence (uppercase, remove whitespace)
    normalized_seq = sequence.upper().replace(" ", "").replace("\n", "").replace("\r", "")

    # Create canonical representation of parameters
    params = (
        f"{normalized_seq}|"
        f"{search_mode}|"
        f"{orientation}|"
        f"{min_tale_length}|"
        f"{max_tale_length}|"
        f"{min_spacer_length}|"
        f"{max_spacer_length}|"
        f"{g_code}|"
        f"{skip_cpg}|"
        f"{skip_consecutive_at}|"
        f"{min_gc}|"
        f"{search_position}|"
        f"{search_position_range}"
    )

    # Generate hash
    return hashlib.sha256(params.encode()).hexdigest()[:16]


class SearchCache(Base):
    """Cache for search results to avoid duplicate computation"""

    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    search_hash = Column(String(16), unique=True, index=True, nullable=False)
    session_id = Column(String(12), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    hit_count = Column(Integer, default=1)
    last_accessed = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_cache_hash", "search_hash"),
        Index("idx_cache_created", "created_at"),
    )


class SearchSession(Base):
    """Stores search metadata and status"""

    __tablename__ = "search_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(12), unique=True, index=True, default=generate_session_id)
    search_hash = Column(String(16), index=True, nullable=True)
    status = Column(String(20), default="pending")  # pending, processing, completed, failed

    # Search parameters
    sequence_length = Column(Integer)
    search_mode = Column(String(10), default="pairs")  # pairs, single
    orientation = Column(String(20), default="convergent")  # any, forward, reverse, convergent, divergent

    # Results
    total_results = Column(Integer, default=0)
    progress = Column(Integer, default=0)  # 0-100
    error_message = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_status_created", "status", "created_at"),
        Index("idx_created_at", "created_at"),
        Index("idx_search_hash", "search_hash"),
    )


class SingleTALE(Base):
    """Stores individual TALE binding sites"""

    __tablename__ = "single_tales"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(12), index=True, nullable=False)

    # Position
    start = Column(Integer, nullable=False)
    end = Column(Integer, nullable=False)
    strand = Column(String(1), nullable=False)  # '+' or '-'

    # Sequence info
    dna_sequence = Column(String(50), nullable=False)
    rvd = Column(String(100), nullable=False)
    tale_length = Column(Integer, nullable=False)

    # Quality metrics
    gc_content = Column(Float, nullable=False)
    g_code = Column(String(2), nullable=False)  # NH or NN

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_single_session", "session_id"),
        Index("idx_single_position", "start", "end"),
        Index("idx_single_strand", "strand"),
    )


class TALEPair(Base):
    """Stores TALE pair results with full orientation support"""

    __tablename__ = "tale_pairs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(12), index=True, nullable=False)

    # Left TALE (first in genomic coordinates)
    left_start = Column(Integer, nullable=False)
    left_end = Column(Integer, nullable=False)
    left_strand = Column(String(1), nullable=False)  # '+' or '-'
    left_dna = Column(String(50), nullable=False)
    left_rvd = Column(String(100), nullable=False)

    # Right TALE (second in genomic coordinates)
    right_start = Column(Integer, nullable=False)
    right_end = Column(Integer, nullable=False)
    right_strand = Column(String(1), nullable=False)  # '+' or '-'
    right_dna = Column(String(50), nullable=False)
    right_rvd = Column(String(100), nullable=False)

    # Pair properties
    spacer_length = Column(Integer, nullable=False)
    tale_length = Column(Integer, nullable=False)
    orientation = Column(String(20), nullable=False)  # convergent, divergent, tandem_forward, tandem_reverse
    g_code = Column(String(2), nullable=False)  # NH or NN

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_pair_session", "session_id", "created_at"),
        Index("idx_pair_left", "left_start", "left_end"),
        Index("idx_pair_right", "right_start", "right_end"),
        Index("idx_pair_spacer", "spacer_length"),
        Index("idx_pair_orientation", "orientation"),
    )


class PlasmidTemplate(Base):
    """Stores plasmid template information"""

    __tablename__ = "plasmid_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)

    # Template type
    template_type = Column(String(50), nullable=False)  # backbone, promoter, effector, terminator
    organism = Column(String(50), nullable=True)  # human, mouse, plant, bacteria, etc.

    # Sequence (stored as text, or file path for large sequences)
    sequence = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)  # Path to template file if sequence is too large

    # Features
    features_json = Column(Text, nullable=True)  # JSON string of sequence features

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index("idx_template_type", "template_type"),
        Index("idx_template_organism", "organism"),
    )
