"""
DNA file format parsers.

Supports:
- FASTA (.fasta, .fa, .fna)
- GenBank (.gb, .gbk, .genbank)
- SnapGene (.dna)
- Plain text
"""

import re
import struct
from typing import Tuple, Optional
from io import BytesIO


def parse_dna_file(content: bytes, filename: str) -> Tuple[str, Optional[str]]:
    """
    Parse DNA sequence from various file formats.

    Args:
        content: File content as bytes
        filename: Original filename (used to determine format)

    Returns:
        Tuple of (sequence, name/description)

    Raises:
        ValueError: If file format is unsupported or parsing fails
    """
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""

    if ext in ("fasta", "fa", "fna", "fas"):
        return parse_fasta(content.decode("utf-8", errors="ignore"))
    elif ext in ("gb", "gbk", "genbank"):
        return parse_genbank(content.decode("utf-8", errors="ignore"))
    elif ext == "dna":
        return parse_snapgene(content)
    elif ext in ("txt", "seq"):
        return parse_plain_text(content.decode("utf-8", errors="ignore"))
    else:
        # Try to auto-detect format
        text = content.decode("utf-8", errors="ignore")
        if text.startswith(">"):
            return parse_fasta(text)
        elif text.startswith("LOCUS"):
            return parse_genbank(text)
        else:
            return parse_plain_text(text)


def parse_fasta(content: str) -> Tuple[str, Optional[str]]:
    """
    Parse FASTA format file.

    Format:
    >header line with description
    SEQUENCE
    CONTINUES HERE
    """
    lines = content.strip().split("\n")
    name = None
    sequence_lines = []

    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            name = line[1:].strip()
        elif line and not line.startswith(";"):  # Skip comment lines
            # Remove any non-sequence characters
            clean_line = re.sub(r"[^ATCGatcgNn]", "", line)
            sequence_lines.append(clean_line)

    sequence = "".join(sequence_lines).upper()

    # Replace N with random base or just remove for TALE search
    sequence = sequence.replace("N", "")

    if not sequence:
        raise ValueError("No valid DNA sequence found in FASTA file")

    return sequence, name


def parse_genbank(content: str) -> Tuple[str, Optional[str]]:
    """
    Parse GenBank format file.

    Extracts:
    - LOCUS name
    - ORIGIN sequence section
    """
    name = None
    sequence_lines = []
    in_origin = False

    for line in content.split("\n"):
        line = line.strip()

        # Extract name from LOCUS line
        if line.startswith("LOCUS"):
            parts = line.split()
            if len(parts) >= 2:
                name = parts[1]

        # Start of sequence
        elif line.startswith("ORIGIN"):
            in_origin = True
            continue

        # End of sequence
        elif line.startswith("//"):
            in_origin = False

        # Sequence line (format: "    1 atcgatcg atcgatcg...")
        elif in_origin:
            # Remove numbers and spaces, keep only sequence
            clean = re.sub(r"[^ATCGatcgNn]", "", line)
            sequence_lines.append(clean)

    sequence = "".join(sequence_lines).upper()
    sequence = sequence.replace("N", "")

    if not sequence:
        raise ValueError("No valid DNA sequence found in GenBank file")

    return sequence, name


def parse_snapgene(content: bytes) -> Tuple[str, Optional[str]]:
    """
    Parse SnapGene .dna file format.

    SnapGene format is a binary format with multiple segments.
    The DNA sequence is stored in a specific segment.
    """
    try:
        f = BytesIO(content)

        # Check magic bytes (SnapGene files start with 0x09)
        magic = f.read(1)
        if magic != b"\x09":
            raise ValueError("Not a valid SnapGene file (incorrect magic byte)")

        # Read header
        header_length = struct.unpack(">I", f.read(4))[0]
        header = f.read(header_length)

        name = None
        sequence = None

        # Parse segments
        while True:
            segment_type = f.read(1)
            if not segment_type:
                break

            segment_type = ord(segment_type)
            segment_length = struct.unpack(">I", f.read(4))[0]
            segment_data = f.read(segment_length)

            # Type 0: DNA sequence
            if segment_type == 0:
                # First byte is topology (0=linear, 1=circular)
                # Rest is sequence
                if len(segment_data) > 1:
                    sequence = segment_data[1:].decode("ascii", errors="ignore")
                    sequence = sequence.upper()
                    sequence = re.sub(r"[^ATCG]", "", sequence)

            # Type 5: Name/description (optional)
            elif segment_type == 5:
                try:
                    name = segment_data.decode("utf-8", errors="ignore")
                except:
                    pass

        if not sequence:
            raise ValueError("No DNA sequence found in SnapGene file")

        return sequence, name

    except struct.error:
        raise ValueError("Invalid SnapGene file format")


def parse_plain_text(content: str) -> Tuple[str, Optional[str]]:
    """
    Parse plain text file containing DNA sequence.

    Removes all non-DNA characters (keeps only A, T, C, G).
    """
    # Remove any whitespace and non-DNA characters
    sequence = re.sub(r"[^ATCGatcgNn]", "", content)
    sequence = sequence.upper()
    sequence = sequence.replace("N", "")

    if not sequence:
        raise ValueError("No valid DNA sequence found in file")

    return sequence, None


def validate_sequence(sequence: str) -> Tuple[bool, str]:
    """
    Validate a DNA sequence.

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sequence:
        return False, "Sequence is empty"

    # Check length
    if len(sequence) < 100:
        return False, f"Sequence too short ({len(sequence)} bp). Minimum is 100 bp."

    if len(sequence) > 100000:
        return False, f"Sequence too long ({len(sequence)} bp). Maximum is 100,000 bp."

    # Check for valid characters
    invalid_chars = set(sequence) - set("ATCG")
    if invalid_chars:
        return False, f"Invalid characters in sequence: {', '.join(invalid_chars)}"

    return True, ""
