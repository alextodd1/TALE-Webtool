"""
NCBI sequence fetcher.

Fetches DNA sequences from NCBI databases using Entrez API.
"""

import httpx
import re
from typing import Tuple, Optional
from urllib.parse import urlencode

# NCBI Entrez base URL
ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Timeout for NCBI requests (seconds)
NCBI_TIMEOUT = 30.0


async def fetch_ncbi_sequence(
    accession: str,
    email: str = "tale-finder@example.com",
) -> Tuple[str, str, dict]:
    """
    Fetch DNA sequence from NCBI by accession number.

    Supports:
    - GenBank accessions (e.g., M21012)
    - RefSeq accessions (e.g., NM_001301717, NC_000001)
    - Gene IDs (e.g., 7157 for TP53)

    Args:
        accession: NCBI accession number or gene ID
        email: Email for NCBI API (required by NCBI policy)

    Returns:
        Tuple of (sequence, description, metadata)

    Raises:
        ValueError: If accession not found or sequence too long
        httpx.HTTPError: If network error occurs
    """
    # Clean accession
    accession = accession.strip().upper()

    # Determine database based on accession format
    db = _guess_database(accession)

    # First, search for the accession to get the GI/ID
    search_url = f"{ENTREZ_BASE}/esearch.fcgi"
    search_params = {
        "db": db,
        "term": accession,
        "retmode": "json",
        "email": email,
    }

    async with httpx.AsyncClient(timeout=NCBI_TIMEOUT) as client:
        # Search for ID
        response = await client.get(search_url, params=search_params)
        response.raise_for_status()

        search_result = response.json()
        id_list = search_result.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            raise ValueError(f"Accession '{accession}' not found in NCBI {db} database")

        ncbi_id = id_list[0]

        # Fetch the sequence in FASTA format
        fetch_url = f"{ENTREZ_BASE}/efetch.fcgi"
        fetch_params = {
            "db": db,
            "id": ncbi_id,
            "rettype": "fasta",
            "retmode": "text",
            "email": email,
        }

        response = await client.get(fetch_url, params=fetch_params)
        response.raise_for_status()

        fasta_content = response.text

        # Parse FASTA
        sequence, description = _parse_fasta_response(fasta_content)

        # Validate sequence length
        if len(sequence) > 100000:
            raise ValueError(
                f"Sequence too long ({len(sequence):,} bp). "
                f"Maximum is 100,000 bp. Consider fetching a specific region."
            )

        if len(sequence) < 100:
            raise ValueError(
                f"Sequence too short ({len(sequence)} bp). Minimum is 100 bp."
            )

        # Get additional metadata
        metadata = {
            "accession": accession,
            "ncbi_id": ncbi_id,
            "database": db,
            "length": len(sequence),
        }

        # Try to get more info from esummary
        try:
            summary_url = f"{ENTREZ_BASE}/esummary.fcgi"
            summary_params = {
                "db": db,
                "id": ncbi_id,
                "retmode": "json",
                "email": email,
            }
            response = await client.get(summary_url, params=summary_params)
            if response.status_code == 200:
                summary = response.json()
                result = summary.get("result", {}).get(ncbi_id, {})
                if result:
                    metadata["title"] = result.get("title", "")
                    metadata["organism"] = result.get("organism", "")
                    metadata["update_date"] = result.get("updatedate", "")
        except:
            pass  # Metadata is optional

        return sequence, description, metadata


async def fetch_ncbi_region(
    accession: str,
    start: int,
    end: int,
    email: str = "tale-finder@example.com",
) -> Tuple[str, str, dict]:
    """
    Fetch a specific region of a sequence from NCBI.

    Args:
        accession: NCBI accession number
        start: Start position (1-based)
        end: End position (1-based, inclusive)
        email: Email for NCBI API

    Returns:
        Tuple of (sequence, description, metadata)
    """
    accession = accession.strip().upper()
    db = _guess_database(accession)

    # Validate region
    if start < 1:
        raise ValueError("Start position must be >= 1")
    if end < start:
        raise ValueError("End position must be >= start position")
    if end - start + 1 > 100000:
        raise ValueError("Region too large. Maximum is 100,000 bp.")

    async with httpx.AsyncClient(timeout=NCBI_TIMEOUT) as client:
        # Search for ID
        search_url = f"{ENTREZ_BASE}/esearch.fcgi"
        search_params = {
            "db": db,
            "term": accession,
            "retmode": "json",
            "email": email,
        }

        response = await client.get(search_url, params=search_params)
        response.raise_for_status()

        search_result = response.json()
        id_list = search_result.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            raise ValueError(f"Accession '{accession}' not found")

        ncbi_id = id_list[0]

        # Fetch region in FASTA format
        fetch_url = f"{ENTREZ_BASE}/efetch.fcgi"
        fetch_params = {
            "db": db,
            "id": ncbi_id,
            "rettype": "fasta",
            "retmode": "text",
            "seq_start": start,
            "seq_stop": end,
            "email": email,
        }

        response = await client.get(fetch_url, params=fetch_params)
        response.raise_for_status()

        fasta_content = response.text
        sequence, description = _parse_fasta_response(fasta_content)

        metadata = {
            "accession": accession,
            "ncbi_id": ncbi_id,
            "database": db,
            "region": f"{start}-{end}",
            "length": len(sequence),
        }

        return sequence, description, metadata


def _guess_database(accession: str) -> str:
    """Guess NCBI database from accession format."""
    accession = accession.upper()

    # RefSeq patterns
    if re.match(r"^N[CGMRPWXYZ]_", accession):
        return "nuccore"

    # Gene ID (numeric only)
    if re.match(r"^\d+$", accession):
        return "gene"

    # GenBank accession patterns
    if re.match(r"^[A-Z]{1,2}\d{5,8}$", accession):
        return "nuccore"

    # Chromosome accessions
    if re.match(r"^NC_", accession):
        return "nuccore"

    # Default to nuccore
    return "nuccore"


def _parse_fasta_response(fasta_content: str) -> Tuple[str, str]:
    """Parse FASTA response from NCBI."""
    lines = fasta_content.strip().split("\n")

    description = ""
    sequence_lines = []

    for line in lines:
        line = line.strip()
        if line.startswith(">"):
            description = line[1:].strip()
        elif line:
            # Clean sequence
            clean = re.sub(r"[^ATCGatcgNn]", "", line)
            sequence_lines.append(clean)

    sequence = "".join(sequence_lines).upper()

    # Remove Ns (ambiguous bases)
    sequence = sequence.replace("N", "")

    if not sequence:
        raise ValueError("No valid DNA sequence found in NCBI response")

    return sequence, description


async def search_ncbi_genes(
    query: str,
    organism: str = "",
    max_results: int = 10,
    email: str = "tale-finder@example.com",
) -> list:
    """
    Search NCBI Gene database.

    Args:
        query: Search term (gene name, symbol, etc.)
        organism: Organism filter (e.g., "Homo sapiens")
        max_results: Maximum number of results
        email: Email for NCBI API

    Returns:
        List of gene info dicts
    """
    search_term = query
    if organism:
        search_term = f"{query}[Gene Name] AND {organism}[Organism]"

    search_url = f"{ENTREZ_BASE}/esearch.fcgi"
    search_params = {
        "db": "gene",
        "term": search_term,
        "retmax": max_results,
        "retmode": "json",
        "email": email,
    }

    async with httpx.AsyncClient(timeout=NCBI_TIMEOUT) as client:
        response = await client.get(search_url, params=search_params)
        response.raise_for_status()

        search_result = response.json()
        id_list = search_result.get("esearchresult", {}).get("idlist", [])

        if not id_list:
            return []

        # Get summaries for all IDs
        summary_url = f"{ENTREZ_BASE}/esummary.fcgi"
        summary_params = {
            "db": "gene",
            "id": ",".join(id_list),
            "retmode": "json",
            "email": email,
        }

        response = await client.get(summary_url, params=summary_params)
        response.raise_for_status()

        summary = response.json()
        results = []

        for gene_id in id_list:
            info = summary.get("result", {}).get(gene_id, {})
            if info:
                results.append({
                    "gene_id": gene_id,
                    "symbol": info.get("name", ""),
                    "description": info.get("description", ""),
                    "organism": info.get("organism", {}).get("scientificname", ""),
                    "chromosome": info.get("chromosome", ""),
                })

        return results
