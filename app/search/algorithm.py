"""Optimized TALE pair finding algorithm"""

from typing import List, Dict, Optional, Callable
from app.search.filters import (
    generate_complementary_dna,
    calculate_gc_content_array,
    precompute_cpg_islands,
    is_in_cpg_island,
    has_consecutive_at,
    get_gc_percentage,
    count_strong_rvds,
    dna_to_rvd,
)


class TALESearchResult:
    """Container for TALE pair result"""

    def __init__(
        self,
        start: int,
        end: int,
        rvd: str,
        comp_start: int,
        comp_end: int,
        comp_rvd: str,
        spacer_length: int,
        tale_length: int,
        g_code: str,
    ):
        self.start = start
        self.end = end
        self.rvd = rvd
        self.comp_start = comp_start
        self.comp_end = comp_end
        self.comp_rvd = comp_rvd
        self.spacer_length = spacer_length
        self.tale_length = tale_length
        self.g_code = g_code


def find_tale_pairs(
    sequence: str,
    min_tale_length: int = 20,
    max_tale_length: int = 20,
    min_spacer_length: int = 30,
    max_spacer_length: int = 30,
    g_code: str = "NH",
    position: Optional[int] = None,
    position_range: Optional[int] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[TALESearchResult]:
    """
    Optimized TALE pair finder with significant performance improvements.

    Optimizations:
    1. Pre-compute CpG islands once (instead of millions of checks)
    2. Pre-compute GC content array for O(1) lookups
    3. Use sliding window approach
    4. Early termination on failed filters
    5. Efficient set-based CpG island lookup

    Args:
        sequence: DNA sequence to search
        min_tale_length: Minimum TALE length
        max_tale_length: Maximum TALE length
        min_spacer_length: Minimum spacer between TALE pairs
        max_spacer_length: Maximum spacer between TALE pairs
        g_code: Guanine code ('NH' or 'NN')
        position: Optional specific position to search around
        position_range: Range around position to search
        progress_callback: Optional callback for progress updates

    Returns:
        List of TALESearchResult objects
    """
    sequence = sequence.upper()
    seq_len = len(sequence)
    pairs = []

    # Step 1: Pre-compute complementary sequence
    comp_sequence = generate_complementary_dna(sequence)

    # Step 2: Pre-compute GC content array (O(n) once, then O(1) queries)
    gc_array = calculate_gc_content_array(sequence)
    comp_gc_array = calculate_gc_content_array(comp_sequence)

    # Step 3: Pre-compute CpG islands (major optimization!)
    cpg_islands = precompute_cpg_islands(sequence, gc_array)
    comp_cpg_islands = precompute_cpg_islands(comp_sequence, comp_gc_array)

    # Step 4: Determine search boundaries
    if position is not None and position_range is not None:
        search_start = max(0, position - position_range)
        search_end = min(seq_len, position + position_range)
    else:
        search_start = 0
        search_end = seq_len

    # Calculate total iterations for progress tracking
    total_iterations = (search_end - search_start) * (max_tale_length - min_tale_length + 1)
    current_iteration = 0

    # Step 5: Main search loop
    for tale_length in range(min_tale_length, max_tale_length + 1):
        for i in range(search_start, search_end):
            # Progress callback
            if progress_callback and current_iteration % 1000 == 0:
                progress = int((current_iteration / total_iterations) * 100)
                progress_callback(progress)

            current_iteration += 1

            # Check if position has enough space for T and TALE
            if i + tale_length + 1 > seq_len:
                break

            # Filter 1: Must have T at position 0 (before TALE)
            if sequence[i] != "T":
                continue

            # Extract TALE region (starts after the T at position 0)
            tale_start = i + 1
            tale_end = i + 1 + tale_length

            # Filter 2: Check for CpG island (O(1) with pre-computed set)
            if is_in_cpg_island(tale_start, tale_length, cpg_islands):
                continue

            # Filter 3: Check for consecutive A/T (7+)
            tale_seq = sequence[tale_start:tale_end]
            if has_consecutive_at(tale_seq):
                continue

            # Filter 4: Check GC content >= 25% (O(1) with pre-computed array)
            gc_pct = get_gc_percentage(gc_array, tale_start, tale_end)
            if gc_pct < 25:
                continue

            # Convert to RVD
            rvd = dna_to_rvd(tale_seq, g_code)

            # Step 6: Search for complementary TALE in antisense strand
            for spacer_length in range(min_spacer_length, max_spacer_length + 1):
                # Calculate complementary position
                comp_start = tale_end + spacer_length
                comp_end = comp_start + tale_length

                # Check bounds
                if comp_end > seq_len:
                    continue

                # Filter 1: Must have A at position 0 on comp strand (T on original)
                if comp_sequence[comp_start - 1] != "A":
                    continue

                # Filter 2: Check CpG island
                if is_in_cpg_island(comp_start, tale_length, comp_cpg_islands):
                    continue

                # Filter 3: Check consecutive A/T
                comp_tale_seq = comp_sequence[comp_start:comp_end]
                if has_consecutive_at(comp_tale_seq):
                    continue

                # Filter 4: Check GC content
                comp_gc_pct = get_gc_percentage(comp_gc_array, comp_start, comp_end)
                if comp_gc_pct < 25:
                    continue

                # Convert to RVD
                comp_rvd = dna_to_rvd(comp_tale_seq, g_code)

                # Filter 5: Check strong RVD count (at least 3 NN or HD per strand)
                if count_strong_rvds(rvd) < 3 or count_strong_rvds(comp_rvd) < 3:
                    continue

                # All filters passed! Add to results
                pairs.append(
                    TALESearchResult(
                        start=tale_start,
                        end=tale_end,
                        rvd=rvd,
                        comp_start=comp_start,
                        comp_end=comp_end,
                        comp_rvd=comp_rvd,
                        spacer_length=spacer_length,
                        tale_length=tale_length,
                        g_code=g_code,
                    )
                )

    # Final progress update
    if progress_callback:
        progress_callback(100)

    return pairs
