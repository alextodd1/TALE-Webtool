"""Pydantic schemas for request/response validation"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re


class SearchRequest(BaseModel):
    """Request schema for TALE search (form-based)"""

    # DNA input
    dna_sequence: Optional[str] = Field(None, max_length=100000)
    ncbi_accession: Optional[str] = Field(None, max_length=50)

    # Search mode
    search_mode: str = Field("pairs", pattern="^(pairs|single)$")
    orientation: str = Field(
        "any",
        pattern="^(any|forward|reverse|convergent|divergent)$"
    )

    # TALE parameters
    min_tale_length: int = Field(15, ge=10, le=30)
    max_tale_length: int = Field(20, ge=10, le=30)
    min_spacer_length: int = Field(14, ge=1, le=100)
    max_spacer_length: int = Field(20, ge=1, le=100)

    # Advanced options
    g_code: str = Field("NH", pattern="^(NH|NN)$")
    position: Optional[int] = Field(None, ge=0)
    position_range: Optional[int] = Field(None, ge=0)
    skip_cpg: bool = Field(True)
    skip_consecutive_at: bool = Field(True)
    min_gc: int = Field(25, ge=0, le=100)

    @field_validator("dna_sequence")
    @classmethod
    def validate_dna(cls, v: Optional[str]) -> Optional[str]:
        """Validate DNA sequence contains only valid bases"""
        if v is None:
            return None
        v = v.upper().strip()
        v = re.sub(r"\s+", "", v)  # Remove whitespace
        if v and not re.match(r"^[ATCG]+$", v):
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


class SingleTALEResponse(BaseModel):
    """Response schema for a single TALE"""

    id: int
    start: int
    end: int
    strand: str
    dna: str
    rvd: str
    length: int
    gc_content: float

    class Config:
        from_attributes = True


class TALEPairResponse(BaseModel):
    """Response schema for a TALE pair"""

    id: int

    # Left TALE
    left_start: int
    left_end: int
    left_strand: str
    left_dna: str
    left_rvd: str

    # Right TALE
    right_start: int
    right_end: int
    right_strand: str
    right_dna: str
    right_rvd: str

    # Pair properties
    spacer_length: int
    tale_length: int
    orientation: str

    class Config:
        from_attributes = True


class SearchSessionResponse(BaseModel):
    """Response schema for search session status"""

    session_id: str
    search_hash: Optional[str] = None
    status: str
    sequence_length: int
    search_mode: str
    orientation: str
    total_results: int
    progress: int
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    cached: bool = False

    class Config:
        from_attributes = True


class PaginatedSingleTALEResponse(BaseModel):
    """Paginated response for single TALEs"""

    session_id: str
    total: int
    page: int
    per_page: int
    total_pages: int
    results: List[SingleTALEResponse]


class PaginatedPairResponse(BaseModel):
    """Paginated response for TALE pairs"""

    session_id: str
    total: int
    page: int
    per_page: int
    total_pages: int
    results: List[TALEPairResponse]


class NCBISearchResult(BaseModel):
    """NCBI gene search result"""

    gene_id: str
    symbol: str
    description: str
    organism: str
    chromosome: str


class PlasmidDesignRequest(BaseModel):
    """Request schema for plasmid design"""

    session_id: str
    tale_id: int

    # Expression system
    organism: str = Field("human")
    promoter: str = Field("cmv")
    backbone: str = Field("pcmv_talen")

    # Effector
    effector: str = Field("foki")

    # Assembly
    assembly: str = Field("golden_gate")
    codon_optimize: bool = Field(True)
    add_nls: bool = Field(True)

    # Output options
    output_genbank: bool = Field(True)
    output_fasta: bool = Field(True)
    output_primers: bool = Field(True)
    output_rvd_order: bool = Field(True)
