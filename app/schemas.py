from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re


class SearchRequest(BaseModel):
    """Request schema for TALE pair search"""

    dna_sequence: str = Field(..., min_length=100, max_length=100000)
    min_tale_length: int = Field(20, ge=10, le=30)
    max_tale_length: int = Field(20, ge=10, le=30)
    min_spacer_length: int = Field(30, ge=1, le=100)
    max_spacer_length: int = Field(30, ge=1, le=100)
    g_code: str = Field("NH", pattern="^(NH|NN)$")
    position: Optional[int] = Field(None, ge=0)
    position_range: Optional[int] = Field(None, ge=0)

    @field_validator("dna_sequence")
    @classmethod
    def validate_dna(cls, v: str) -> str:
        """Validate DNA sequence contains only valid bases"""
        v = v.upper().strip()
        if not re.match(r"^[ATCG]+$", v):
            raise ValueError("DNA sequence must contain only A, T, C, G characters")
        return v

    @field_validator("max_tale_length")
    @classmethod
    def validate_tale_range(cls, v: int, info) -> int:
        """Ensure max_tale_length >= min_tale_length"""
        if "min_tale_length" in info.data and v < info.data["min_tale_length"]:
            raise ValueError("max_tale_length must be >= min_tale_length")
        return v

    @field_validator("max_spacer_length")
    @classmethod
    def validate_spacer_range(cls, v: int, info) -> int:
        """Ensure max_spacer_length >= min_spacer_length"""
        if "min_spacer_length" in info.data and v < info.data["min_spacer_length"]:
            raise ValueError("max_spacer_length must be >= min_spacer_length")
        return v


class TALEPairResponse(BaseModel):
    """Response schema for a single TALE pair"""

    id: int
    start: int
    end: int
    rvd: str
    comp_start: int
    comp_end: int
    comp_rvd: str
    spacer_length: int
    tale_length: int
    g_code: str

    class Config:
        from_attributes = True


class SearchSessionResponse(BaseModel):
    """Response schema for search session status"""

    session_id: str
    status: str
    sequence_length: int
    total_pairs: int
    progress: int
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SearchInitResponse(BaseModel):
    """Response when search is initiated"""

    session_id: str
    message: str
    status: str


class PaginatedResponse(BaseModel):
    """Paginated response for TALE pairs"""

    session_id: str
    total: int
    page: int
    per_page: int
    total_pages: int
    pairs: List[TALEPairResponse]
