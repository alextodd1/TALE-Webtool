"""Optimized filters for TALE pair validation"""

import re
from typing import List, Set
from functools import lru_cache

# Compiled regex for consecutive A/T detection (7 or more)
CONSECUTIVE_AT_PATTERN = re.compile(r"[AT]{7,}")


def generate_complementary_dna(sequence: str) -> str:
    """Generate complementary DNA strand (same direction)"""
    complement = {"A": "T", "T": "A", "C": "G", "G": "C"}
    return "".join(complement.get(base, base) for base in sequence)


def reverse_complement(sequence: str) -> str:
    """Generate reverse complement of DNA sequence (5' to 3' on opposite strand)"""
    complement = {"A": "T", "T": "A", "C": "G", "G": "C"}
    return "".join(complement.get(base, base) for base in reversed(sequence))


def calculate_gc_content_array(sequence: str) -> List[int]:
    """
    Pre-compute cumulative GC count for O(1) range queries.
    Returns array where gc_array[i] = number of G/C bases from 0 to i.
    """
    gc_count = 0
    gc_array = [0]

    for base in sequence:
        if base in "GC":
            gc_count += 1
        gc_array.append(gc_count)

    return gc_array


def get_gc_percentage(gc_array: List[int], start: int, end: int) -> float:
    """
    Calculate GC% for a region using pre-computed array.
    O(1) time complexity.
    """
    length = end - start
    if length == 0:
        return 0.0

    gc_count = gc_array[end] - gc_array[start]
    return (gc_count / length) * 100


def precompute_cpg_islands(sequence: str, gc_array: List[int], window_size: int = 200) -> Set[int]:
    """
    Pre-compute all CpG island positions.
    Returns a set of positions that are within CpG islands.

    CpG island criteria:
    - Length >= 200bp
    - GC content >= 50%
    - Observed/Expected CpG ratio >= 0.6
    """
    cpg_positions = set()
    seq_len = len(sequence)

    # Scan sequence with sliding window
    for i in range(seq_len - window_size + 1):
        region = sequence[i : i + window_size]

        # Check GC content
        gc_pct = get_gc_percentage(gc_array, i, i + window_size)
        if gc_pct < 50:
            continue

        # Calculate CpG ratio
        cpg_count = region.count("CG")
        c_count = region.count("C")
        g_count = region.count("G")

        if c_count == 0 or g_count == 0:
            continue

        expected_cpg = (c_count * g_count) / window_size
        if expected_cpg == 0:
            continue

        observed_expected_ratio = cpg_count / expected_cpg

        # If this is a CpG island, mark all positions in window
        if observed_expected_ratio >= 0.6:
            for pos in range(i, i + window_size):
                cpg_positions.add(pos)

    return cpg_positions


def is_in_cpg_island(position: int, tale_length: int, cpg_positions: Set[int], buffer: int = 100) -> bool:
    """
    Check if TALE region overlaps with CpG island using pre-computed positions.
    O(1) average case with set lookup.
    """
    # Check region with buffer
    start = max(0, position - buffer)
    end = position + tale_length + buffer

    # Check if any position in range is in CpG island
    for pos in range(start, end, 10):  # Sample every 10bp for efficiency
        if pos in cpg_positions:
            return True

    return False


def has_consecutive_at(sequence: str) -> bool:
    """Check for 7+ consecutive A or T bases using compiled regex"""
    return CONSECUTIVE_AT_PATTERN.search(sequence) is not None


def count_strong_rvds(rvd_sequence: str) -> int:
    """
    Count strong RVD pairs (NN and HD).
    NN and HD provide stronger, more specific DNA binding.
    """
    # Split into 2-character RVD codes
    rvd_pairs = [rvd_sequence[i : i + 2] for i in range(0, len(rvd_sequence), 2)]
    return sum(1 for rvd in rvd_pairs if rvd in ("NN", "HD"))


# RVD encoding mapping
@lru_cache(maxsize=None)
def get_rvd_mapping() -> dict:
    """Get RVD (Repeat Variable Diresidue) to DNA base mapping"""
    return {
        "A": "NI",  # Asparagine-Isoleucine for Adenine
        "C": "HD",  # Histidine-Aspartate for Cytosine
        "G": "NN",  # Asparagine-Asparagine for Guanine (or NH)
        "T": "NG",  # Asparagine-Glycine for Thymine
    }


def dna_to_rvd(sequence: str, g_code: str = "NH") -> str:
    """
    Convert DNA sequence to RVD sequence.

    Args:
        sequence: DNA sequence string
        g_code: Code for Guanine - either 'NH' or 'NN'

    Returns:
        RVD sequence as string
    """
    rvd_map = get_rvd_mapping()

    # Override G mapping based on g_code
    if g_code == "NH":
        rvd_map = {**rvd_map, "G": "NH"}

    return "".join(rvd_map.get(base, "XX") for base in sequence)
