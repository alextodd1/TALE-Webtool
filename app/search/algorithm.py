"""
TALE binding site finder algorithm.

Supports:
- Single TALE finding (any orientation)
- TALE pair finding (all orientation combinations)
- Configurable filters
"""

from typing import List, Optional, Callable
from dataclasses import dataclass
from app.search.filters import (
    generate_complementary_dna,
    reverse_complement,
    calculate_gc_content_array,
    precompute_cpg_islands,
    is_in_cpg_island,
    has_consecutive_at,
    get_gc_percentage,
    count_strong_rvds,
    dna_to_rvd,
)


@dataclass
class SingleTALEResult:
    """Container for single TALE result"""
    start: int
    end: int
    strand: str  # '+' or '-'
    dna_sequence: str
    rvd: str
    tale_length: int
    gc_content: float
    g_code: str


@dataclass
class TALEPairResult:
    """Container for TALE pair result"""
    # Left TALE (first in genomic coordinates)
    left_start: int
    left_end: int
    left_strand: str
    left_dna: str
    left_rvd: str

    # Right TALE (second in genomic coordinates)
    right_start: int
    right_end: int
    right_strand: str
    right_dna: str
    right_rvd: str

    # Pair properties
    spacer_length: int
    tale_length: int
    orientation: str  # convergent, divergent, tandem_forward, tandem_reverse
    g_code: str


def find_single_tales(
    sequence: str,
    min_tale_length: int = 15,
    max_tale_length: int = 20,
    g_code: str = "NH",
    orientation: str = "any",  # any, forward, reverse
    skip_cpg: bool = True,
    skip_consecutive_at: bool = True,
    min_gc: int = 25,
    position: Optional[int] = None,
    position_range: Optional[int] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[SingleTALEResult]:
    """
    Find all valid single TALE binding sites in a sequence.

    Args:
        sequence: DNA sequence to search
        min_tale_length: Minimum TALE length (10-30)
        max_tale_length: Maximum TALE length (10-30)
        g_code: Guanine code ('NH' or 'NN')
        orientation: Which strand(s) to search ('any', 'forward', 'reverse')
        skip_cpg: Whether to skip CpG islands
        skip_consecutive_at: Whether to skip sequences with 7+ consecutive A/T
        min_gc: Minimum GC content percentage
        position: Optional specific position to search around
        position_range: Range around position to search
        progress_callback: Optional callback for progress updates

    Returns:
        List of SingleTALEResult objects
    """
    sequence = sequence.upper()
    seq_len = len(sequence)
    results = []

    # Pre-compute arrays for O(1) lookups
    gc_array = calculate_gc_content_array(sequence)
    cpg_islands = precompute_cpg_islands(sequence, gc_array) if skip_cpg else set()

    # Determine search boundaries
    if position is not None and position_range is not None:
        search_start = max(0, position - position_range)
        search_end = min(seq_len, position + position_range)
    else:
        search_start = 0
        search_end = seq_len

    # Calculate total iterations for progress
    tale_lengths = range(min_tale_length, max_tale_length + 1)
    strands_to_search = []
    if orientation in ("any", "forward"):
        strands_to_search.append("+")
    if orientation in ("any", "reverse"):
        strands_to_search.append("-")

    total_iterations = (search_end - search_start) * len(tale_lengths) * len(strands_to_search)
    current_iteration = 0

    # Search forward strand
    if "+" in strands_to_search:
        for tale_length in tale_lengths:
            for i in range(search_start, search_end):
                if progress_callback and current_iteration % 1000 == 0:
                    progress = int((current_iteration / total_iterations) * 100)
                    progress_callback(progress)
                current_iteration += 1

                # Check bounds
                if i + tale_length + 1 > seq_len:
                    break

                # Filter 1: Must have T at position 0 (before TALE)
                if sequence[i] != "T":
                    continue

                tale_start = i + 1
                tale_end = i + 1 + tale_length
                tale_seq = sequence[tale_start:tale_end]

                # Apply filters
                result = _validate_tale(
                    tale_seq, tale_start, tale_end, "+",
                    gc_array, cpg_islands,
                    skip_cpg, skip_consecutive_at, min_gc, g_code
                )
                if result:
                    results.append(result)

    # Search reverse strand (find TALEs that bind on the minus strand)
    if "-" in strands_to_search:
        # Generate reverse complement and its arrays
        rev_comp = reverse_complement(sequence)
        rev_gc_array = calculate_gc_content_array(rev_comp)
        rev_cpg_islands = precompute_cpg_islands(rev_comp, rev_gc_array) if skip_cpg else set()

        for tale_length in tale_lengths:
            for i in range(search_start, search_end):
                if progress_callback and current_iteration % 1000 == 0:
                    progress = int((current_iteration / total_iterations) * 100)
                    progress_callback(progress)
                current_iteration += 1

                # Check bounds
                if i + tale_length + 1 > seq_len:
                    break

                # For reverse strand, we look for T on the reverse complement
                # Position on reverse complement
                rev_i = seq_len - 1 - i

                if rev_i - tale_length < 0:
                    continue

                if rev_comp[rev_i] != "T":
                    continue

                # Extract TALE sequence from reverse complement
                tale_end_rev = rev_i
                tale_start_rev = rev_i - tale_length
                tale_seq = rev_comp[tale_start_rev:tale_end_rev]

                # Convert back to forward strand coordinates
                # The TALE binds at positions (seq_len - tale_end_rev) to (seq_len - tale_start_rev)
                forward_start = seq_len - tale_end_rev
                forward_end = seq_len - tale_start_rev

                # Apply filters
                result = _validate_tale(
                    tale_seq, forward_start, forward_end, "-",
                    rev_gc_array, rev_cpg_islands,
                    skip_cpg, skip_consecutive_at, min_gc, g_code,
                    rev_pos_start=tale_start_rev, rev_pos_end=tale_end_rev
                )
                if result:
                    results.append(result)

    if progress_callback:
        progress_callback(100)

    return results


def _validate_tale(
    tale_seq: str,
    start: int,
    end: int,
    strand: str,
    gc_array: List[int],
    cpg_islands: set,
    skip_cpg: bool,
    skip_consecutive_at: bool,
    min_gc: int,
    g_code: str,
    rev_pos_start: Optional[int] = None,
    rev_pos_end: Optional[int] = None,
) -> Optional[SingleTALEResult]:
    """Validate a potential TALE and return result if valid."""

    tale_length = len(tale_seq)

    # Use reverse positions for filter checks if provided
    check_start = rev_pos_start if rev_pos_start is not None else start
    check_end = rev_pos_end if rev_pos_end is not None else end

    # Filter: CpG island check
    if skip_cpg and is_in_cpg_island(check_start, tale_length, cpg_islands):
        return None

    # Filter: Consecutive A/T check
    if skip_consecutive_at and has_consecutive_at(tale_seq):
        return None

    # Filter: GC content check
    gc_pct = get_gc_percentage(gc_array, check_start, check_end)
    if gc_pct < min_gc:
        return None

    # Convert to RVD
    rvd = dna_to_rvd(tale_seq, g_code)

    return SingleTALEResult(
        start=start,
        end=end,
        strand=strand,
        dna_sequence=tale_seq,
        rvd=rvd,
        tale_length=tale_length,
        gc_content=round(gc_pct, 1),
        g_code=g_code,
    )


def find_tale_pairs(
    sequence: str,
    min_tale_length: int = 15,
    max_tale_length: int = 20,
    min_spacer_length: int = 14,
    max_spacer_length: int = 20,
    g_code: str = "NH",
    orientation: str = "any",  # any, convergent, divergent, tandem_forward, tandem_reverse
    skip_cpg: bool = True,
    skip_consecutive_at: bool = True,
    min_gc: int = 25,
    position: Optional[int] = None,
    position_range: Optional[int] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> List[TALEPairResult]:
    """
    Find TALE pairs in all requested orientations.

    Orientations:
    - convergent: Left on + strand, Right on - strand, facing each other (standard TALEN)
    - divergent: Left on - strand, Right on + strand, facing away
    - tandem_forward: Both on + strand
    - tandem_reverse: Both on - strand
    - any: All of the above

    Args:
        sequence: DNA sequence to search
        min_tale_length: Minimum TALE length
        max_tale_length: Maximum TALE length
        min_spacer_length: Minimum spacer between TALE pairs
        max_spacer_length: Maximum spacer between TALE pairs
        g_code: Guanine code ('NH' or 'NN')
        orientation: Pair orientation to find
        skip_cpg: Whether to skip CpG islands
        skip_consecutive_at: Whether to skip 7+ consecutive A/T
        min_gc: Minimum GC content percentage
        position: Optional specific position to search around
        position_range: Range around position to search
        progress_callback: Optional callback for progress updates

    Returns:
        List of TALEPairResult objects
    """
    sequence = sequence.upper()
    seq_len = len(sequence)
    pairs = []

    # Pre-compute for forward strand
    gc_array = calculate_gc_content_array(sequence)
    cpg_islands = precompute_cpg_islands(sequence, gc_array) if skip_cpg else set()

    # Pre-compute for reverse strand
    rev_comp = reverse_complement(sequence)
    rev_gc_array = calculate_gc_content_array(rev_comp)
    rev_cpg_islands = precompute_cpg_islands(rev_comp, rev_gc_array) if skip_cpg else set()

    # First, find all valid single TALEs on both strands
    forward_tales = _find_all_tales_on_strand(
        sequence, "+", gc_array, cpg_islands,
        min_tale_length, max_tale_length,
        skip_cpg, skip_consecutive_at, min_gc, g_code,
        position, position_range
    )

    reverse_tales = _find_all_tales_on_strand(
        sequence, "-", rev_gc_array, rev_cpg_islands,
        min_tale_length, max_tale_length,
        skip_cpg, skip_consecutive_at, min_gc, g_code,
        position, position_range, rev_comp
    )

    # Calculate total pair combinations for progress
    total_combinations = 0
    orientations_to_check = []

    if orientation in ("any", "convergent"):
        orientations_to_check.append("convergent")
        total_combinations += len(forward_tales) * len(reverse_tales)
    if orientation in ("any", "divergent"):
        orientations_to_check.append("divergent")
        total_combinations += len(reverse_tales) * len(forward_tales)
    if orientation in ("any", "tandem_forward"):
        orientations_to_check.append("tandem_forward")
        total_combinations += len(forward_tales) * len(forward_tales)
    if orientation in ("any", "tandem_reverse"):
        orientations_to_check.append("tandem_reverse")
        total_combinations += len(reverse_tales) * len(reverse_tales)

    current_iteration = 0

    # Convergent: Left (+) ... spacer ... Right (-)
    # Standard TALEN configuration
    if "convergent" in orientations_to_check:
        for left in forward_tales:
            for right in reverse_tales:
                if progress_callback and current_iteration % 1000 == 0:
                    progress_callback(int((current_iteration / max(1, total_combinations)) * 100))
                current_iteration += 1

                # Right must be downstream of left
                spacer = right.start - left.end
                if min_spacer_length <= spacer <= max_spacer_length:
                    if left.tale_length == right.tale_length:
                        pairs.append(TALEPairResult(
                            left_start=left.start,
                            left_end=left.end,
                            left_strand=left.strand,
                            left_dna=left.dna_sequence,
                            left_rvd=left.rvd,
                            right_start=right.start,
                            right_end=right.end,
                            right_strand=right.strand,
                            right_dna=right.dna_sequence,
                            right_rvd=right.rvd,
                            spacer_length=spacer,
                            tale_length=left.tale_length,
                            orientation="convergent",
                            g_code=g_code,
                        ))

    # Divergent: Left (-) ... spacer ... Right (+)
    if "divergent" in orientations_to_check:
        for left in reverse_tales:
            for right in forward_tales:
                if progress_callback and current_iteration % 1000 == 0:
                    progress_callback(int((current_iteration / max(1, total_combinations)) * 100))
                current_iteration += 1

                # Right must be downstream of left
                spacer = right.start - left.end
                if min_spacer_length <= spacer <= max_spacer_length:
                    if left.tale_length == right.tale_length:
                        pairs.append(TALEPairResult(
                            left_start=left.start,
                            left_end=left.end,
                            left_strand=left.strand,
                            left_dna=left.dna_sequence,
                            left_rvd=left.rvd,
                            right_start=right.start,
                            right_end=right.end,
                            right_strand=right.strand,
                            right_dna=right.dna_sequence,
                            right_rvd=right.rvd,
                            spacer_length=spacer,
                            tale_length=left.tale_length,
                            orientation="divergent",
                            g_code=g_code,
                        ))

    # Tandem forward: Left (+) ... spacer ... Right (+)
    if "tandem_forward" in orientations_to_check:
        for i, left in enumerate(forward_tales):
            for right in forward_tales[i+1:]:  # Only pairs where right is after left
                if progress_callback and current_iteration % 1000 == 0:
                    progress_callback(int((current_iteration / max(1, total_combinations)) * 100))
                current_iteration += 1

                spacer = right.start - left.end
                if min_spacer_length <= spacer <= max_spacer_length:
                    if left.tale_length == right.tale_length:
                        pairs.append(TALEPairResult(
                            left_start=left.start,
                            left_end=left.end,
                            left_strand=left.strand,
                            left_dna=left.dna_sequence,
                            left_rvd=left.rvd,
                            right_start=right.start,
                            right_end=right.end,
                            right_strand=right.strand,
                            right_dna=right.dna_sequence,
                            right_rvd=right.rvd,
                            spacer_length=spacer,
                            tale_length=left.tale_length,
                            orientation="tandem_forward",
                            g_code=g_code,
                        ))

    # Tandem reverse: Left (-) ... spacer ... Right (-)
    if "tandem_reverse" in orientations_to_check:
        for i, left in enumerate(reverse_tales):
            for right in reverse_tales[i+1:]:
                if progress_callback and current_iteration % 1000 == 0:
                    progress_callback(int((current_iteration / max(1, total_combinations)) * 100))
                current_iteration += 1

                spacer = right.start - left.end
                if min_spacer_length <= spacer <= max_spacer_length:
                    if left.tale_length == right.tale_length:
                        pairs.append(TALEPairResult(
                            left_start=left.start,
                            left_end=left.end,
                            left_strand=left.strand,
                            left_dna=left.dna_sequence,
                            left_rvd=left.rvd,
                            right_start=right.start,
                            right_end=right.end,
                            right_strand=right.strand,
                            right_dna=right.dna_sequence,
                            right_rvd=right.rvd,
                            spacer_length=spacer,
                            tale_length=left.tale_length,
                            orientation="tandem_reverse",
                            g_code=g_code,
                        ))

    if progress_callback:
        progress_callback(100)

    # Sort by position
    pairs.sort(key=lambda p: (p.left_start, p.right_start))

    return pairs


def _find_all_tales_on_strand(
    sequence: str,
    strand: str,
    gc_array: List[int],
    cpg_islands: set,
    min_tale_length: int,
    max_tale_length: int,
    skip_cpg: bool,
    skip_consecutive_at: bool,
    min_gc: int,
    g_code: str,
    position: Optional[int],
    position_range: Optional[int],
    rev_comp: Optional[str] = None,
) -> List[SingleTALEResult]:
    """Find all valid TALEs on a specific strand."""

    seq_len = len(sequence)
    results = []

    # Determine search boundaries
    if position is not None and position_range is not None:
        search_start = max(0, position - position_range)
        search_end = min(seq_len, position + position_range)
    else:
        search_start = 0
        search_end = seq_len

    if strand == "+":
        # Search forward strand
        for tale_length in range(min_tale_length, max_tale_length + 1):
            for i in range(search_start, search_end):
                if i + tale_length + 1 > seq_len:
                    break

                # Must have T before TALE
                if sequence[i] != "T":
                    continue

                tale_start = i + 1
                tale_end = i + 1 + tale_length
                tale_seq = sequence[tale_start:tale_end]

                result = _validate_tale(
                    tale_seq, tale_start, tale_end, "+",
                    gc_array, cpg_islands,
                    skip_cpg, skip_consecutive_at, min_gc, g_code
                )
                if result:
                    # Additional filter: require strong RVDs
                    if count_strong_rvds(result.rvd) >= 3:
                        results.append(result)

    else:
        # Search reverse strand
        if rev_comp is None:
            rev_comp = reverse_complement(sequence)

        for tale_length in range(min_tale_length, max_tale_length + 1):
            for i in range(search_start, search_end):
                # Position on reverse complement
                rev_i = seq_len - 1 - i

                if rev_i - tale_length < 0:
                    continue

                if rev_comp[rev_i] != "T":
                    continue

                # Extract TALE from reverse complement
                tale_end_rev = rev_i
                tale_start_rev = rev_i - tale_length
                tale_seq = rev_comp[tale_start_rev:tale_end_rev]

                # Convert to forward strand coordinates
                forward_start = seq_len - tale_end_rev
                forward_end = seq_len - tale_start_rev

                result = _validate_tale(
                    tale_seq, forward_start, forward_end, "-",
                    gc_array, cpg_islands,
                    skip_cpg, skip_consecutive_at, min_gc, g_code,
                    rev_pos_start=tale_start_rev, rev_pos_end=tale_end_rev
                )
                if result:
                    if count_strong_rvds(result.rvd) >= 3:
                        results.append(result)

    # Sort by position
    results.sort(key=lambda t: t.start)

    return results
