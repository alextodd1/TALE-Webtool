"""Main FastAPI application - TALE Finder"""

from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional
from datetime import datetime
import pandas as pd
from io import StringIO

from app.database import init_db, close_db, get_db
from app.models import (
    SearchSession,
    SearchCache,
    TALEPair,
    SingleTALE,
    generate_session_id,
    generate_search_hash,
)
from app.schemas import SearchSessionResponse
from app.search import find_tale_pairs, find_single_tales
from app.file_parsers import parse_dna_file, validate_sequence
from app.ncbi_fetch import fetch_ncbi_sequence, search_ncbi_genes
from app.config import get_settings
from app.logging_config import setup_logging, get_logger

settings = get_settings()

# Initialize logging
setup_logging(log_level=settings.debug and "DEBUG" or "INFO")
logger = get_logger(__name__)

# Scheduler for periodic tasks
scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    await init_db()
    logger.info("Database initialized successfully")

    # Schedule cleanup task
    from app.database import async_session_maker
    from app.tasks import cleanup_old_sessions

    async def cleanup_job():
        async with async_session_maker() as db:
            await cleanup_old_sessions(db)

    scheduler.add_job(cleanup_job, "cron", hour=2, minute=0)
    scheduler.start()
    logger.info("Cleanup scheduler started")

    yield

    scheduler.shutdown()
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="TALE Finder",
    description="Find TALE binding sites in DNA sequences",
    version="3.0.0",
    lifespan=lifespan,
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main search page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """Serve about page"""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Serve help page"""
    return templates.TemplateResponse("about.html", {"request": request})


@app.post("/search")
async def perform_search(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Form fields
    input_method: str = Form("paste"),
    dna_sequence: Optional[str] = Form(None),
    dna_file: Optional[UploadFile] = File(None),
    ncbi_accession: Optional[str] = Form(None),
    search_mode: str = Form("pairs"),
    orientation: str = Form("any"),
    min_tale_length: int = Form(15),
    max_tale_length: int = Form(20),
    min_spacer_length: int = Form(14),
    max_spacer_length: int = Form(20),
    g_code: str = Form("NH"),
    position: Optional[int] = Form(None),
    position_range: Optional[int] = Form(None),
    skip_cpg: bool = Form(True),
    skip_consecutive_at: bool = Form(True),
    min_gc: int = Form(25),
):
    """
    Handle search form submission.
    Supports paste, file upload, and NCBI fetch.
    """
    sequence = None
    sequence_name = None
    error = None

    try:
        # Get sequence based on input method
        if input_method == "paste":
            if not dna_sequence or not dna_sequence.strip():
                raise ValueError("Please enter a DNA sequence")
            sequence = dna_sequence.upper().replace(" ", "").replace("\n", "").replace("\r", "")

        elif input_method == "file":
            if not dna_file or not dna_file.filename:
                raise ValueError("Please upload a DNA file")
            content = await dna_file.read()
            sequence, sequence_name = parse_dna_file(content, dna_file.filename)

        elif input_method == "ncbi":
            if not ncbi_accession or not ncbi_accession.strip():
                raise ValueError("Please enter an NCBI accession number")
            sequence, sequence_name, _ = await fetch_ncbi_sequence(ncbi_accession.strip())

        else:
            raise ValueError(f"Unknown input method: {input_method}")

        # Validate sequence
        is_valid, error_msg = validate_sequence(sequence)
        if not is_valid:
            raise ValueError(error_msg)

        # Generate search hash for caching
        search_hash = generate_search_hash(
            sequence=sequence,
            search_mode=search_mode,
            orientation=orientation,
            min_tale_length=min_tale_length,
            max_tale_length=max_tale_length,
            min_spacer_length=min_spacer_length,
            max_spacer_length=max_spacer_length,
            g_code=g_code,
            skip_cpg=skip_cpg,
            skip_consecutive_at=skip_consecutive_at,
            min_gc=min_gc,
        )

        # Check cache for existing results
        cache_result = await db.execute(
            select(SearchCache).where(SearchCache.search_hash == search_hash)
        )
        cached = cache_result.scalar_one_or_none()

        if cached:
            # Update cache hit count
            cached.hit_count += 1
            cached.last_accessed = datetime.utcnow()
            await db.commit()

            # Redirect to cached results
            logger.info(f"Cache hit for hash {search_hash}, redirecting to session {cached.session_id}")
            return RedirectResponse(
                url=f"/results/{cached.session_id}?cached=1",
                status_code=303
            )

        # Create new session
        session_id = generate_session_id()

        search_session = SearchSession(
            session_id=session_id,
            search_hash=search_hash,
            status="processing",
            sequence_length=len(sequence),
            search_mode=search_mode,
            orientation=orientation,
        )
        db.add(search_session)
        await db.commit()

        # Perform search
        logger.info(f"Starting {search_mode} search for session {session_id}")

        if search_mode == "single":
            # Map orientation for single TALE search
            single_orientation = orientation
            if orientation in ("convergent", "divergent"):
                single_orientation = "any"

            results = find_single_tales(
                sequence=sequence,
                min_tale_length=min_tale_length,
                max_tale_length=max_tale_length,
                g_code=g_code,
                orientation=single_orientation,
                skip_cpg=skip_cpg,
                skip_consecutive_at=skip_consecutive_at,
                min_gc=min_gc,
                position=position,
                position_range=position_range,
            )

            # Store results
            for result in results:
                db.add(SingleTALE(
                    session_id=session_id,
                    start=result.start,
                    end=result.end,
                    strand=result.strand,
                    dna_sequence=result.dna_sequence,
                    rvd=result.rvd,
                    tale_length=result.tale_length,
                    gc_content=result.gc_content,
                    g_code=result.g_code,
                ))

        else:
            # Pair search
            results = find_tale_pairs(
                sequence=sequence,
                min_tale_length=min_tale_length,
                max_tale_length=max_tale_length,
                min_spacer_length=min_spacer_length,
                max_spacer_length=max_spacer_length,
                g_code=g_code,
                orientation=orientation,
                skip_cpg=skip_cpg,
                skip_consecutive_at=skip_consecutive_at,
                min_gc=min_gc,
                position=position,
                position_range=position_range,
            )

            # Store results
            for result in results:
                db.add(TALEPair(
                    session_id=session_id,
                    left_start=result.left_start,
                    left_end=result.left_end,
                    left_strand=result.left_strand,
                    left_dna=result.left_dna,
                    left_rvd=result.left_rvd,
                    right_start=result.right_start,
                    right_end=result.right_end,
                    right_strand=result.right_strand,
                    right_dna=result.right_dna,
                    right_rvd=result.right_rvd,
                    spacer_length=result.spacer_length,
                    tale_length=result.tale_length,
                    orientation=result.orientation,
                    g_code=result.g_code,
                ))

        # Update session
        search_session.status = "completed"
        search_session.total_results = len(results)
        search_session.progress = 100
        search_session.completed_at = datetime.utcnow()

        # Add to cache
        db.add(SearchCache(
            search_hash=search_hash,
            session_id=session_id,
        ))

        await db.commit()

        logger.info(f"Search completed for session {session_id}: {len(results)} results")

        return RedirectResponse(url=f"/results/{session_id}", status_code=303)

    except ValueError as e:
        error = str(e)
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        error = f"Search failed: {str(e)}"

    # Return to form with error
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "error": error,
            "dna_sequence": dna_sequence,
        }
    )


@app.get("/results/{session_id}", response_class=HTMLResponse)
async def show_results(
    request: Request,
    session_id: str,
    page: int = 1,
    cached: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Display search results"""
    # Get session
    result = await db.execute(
        select(SearchSession).where(SearchSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    per_page = 50
    offset = (page - 1) * per_page

    if session.search_mode == "single":
        # Get single TALE results
        count_result = await db.execute(
            select(func.count(SingleTALE.id)).where(SingleTALE.session_id == session_id)
        )
        total = count_result.scalar()

        results_query = await db.execute(
            select(SingleTALE)
            .where(SingleTALE.session_id == session_id)
            .order_by(SingleTALE.start)
            .offset(offset)
            .limit(per_page)
        )
        results = [
            {
                "id": r.id,
                "start": r.start,
                "end": r.end,
                "strand": r.strand,
                "dna": r.dna_sequence,
                "rvd": r.rvd,
                "length": r.tale_length,
                "gc_content": r.gc_content,
            }
            for r in results_query.scalars().all()
        ]
    else:
        # Get pair results
        count_result = await db.execute(
            select(func.count(TALEPair.id)).where(TALEPair.session_id == session_id)
        )
        total = count_result.scalar()

        results_query = await db.execute(
            select(TALEPair)
            .where(TALEPair.session_id == session_id)
            .order_by(TALEPair.left_start)
            .offset(offset)
            .limit(per_page)
        )
        results = [
            {
                "id": r.id,
                "left_start": r.left_start,
                "left_end": r.left_end,
                "left_strand": r.left_strand,
                "left_dna": r.left_dna,
                "left_rvd": r.left_rvd,
                "right_start": r.right_start,
                "right_end": r.right_end,
                "right_strand": r.right_strand,
                "right_dna": r.right_dna,
                "right_rvd": r.right_rvd,
                "spacer_length": r.spacer_length,
                "orientation": r.orientation,
            }
            for r in results_query.scalars().all()
        ]

    page_count = (total + per_page - 1) // per_page

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "session_id": session_id,
            "search_hash": session.search_hash,
            "sequence_length": session.sequence_length,
            "search_mode": session.search_mode,
            "orientation": session.orientation,
            "total_results": total,
            "results": results,
            "page": page,
            "page_count": page_count,
            "cached": bool(cached),
            "min_tale_length": 15,  # These would be stored in session ideally
            "max_tale_length": 20,
            "min_spacer_length": 14,
            "max_spacer_length": 20,
            "g_code": "NH",
        }
    )


@app.get("/design/{session_id}/{tale_id}", response_class=HTMLResponse)
async def design_plasmid(
    request: Request,
    session_id: str,
    tale_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Show plasmid design page"""
    # Get session
    session_result = await db.execute(
        select(SearchSession).where(SearchSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the TALE/pair
    if session.search_mode == "single":
        tale_result = await db.execute(
            select(SingleTALE).where(
                SingleTALE.session_id == session_id,
                SingleTALE.id == tale_id
            )
        )
        tale = tale_result.scalar_one_or_none()
        if not tale:
            raise HTTPException(status_code=404, detail="TALE not found")

        tale_data = {
            "start": tale.start,
            "end": tale.end,
            "strand": tale.strand,
            "rvd": tale.rvd,
            "dna": tale.dna_sequence,
        }
        tale_type = "single"
    else:
        pair_result = await db.execute(
            select(TALEPair).where(
                TALEPair.session_id == session_id,
                TALEPair.id == tale_id
            )
        )
        pair = pair_result.scalar_one_or_none()
        if not pair:
            raise HTTPException(status_code=404, detail="TALE pair not found")

        tale_data = {
            "left_start": pair.left_start,
            "left_end": pair.left_end,
            "left_strand": pair.left_strand,
            "left_rvd": pair.left_rvd,
            "right_start": pair.right_start,
            "right_end": pair.right_end,
            "right_strand": pair.right_strand,
            "right_rvd": pair.right_rvd,
            "spacer_length": pair.spacer_length,
        }
        tale_type = "pair"

    return templates.TemplateResponse(
        "design.html",
        {
            "request": request,
            "session_id": session_id,
            "tale_id": tale_id,
            "tale": tale_data,
            "tale_type": tale_type,
        }
    )


@app.get("/export/{session_id}")
async def export_results(
    session_id: str,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
):
    """Export results as CSV, TSV, or FASTA"""
    # Get session
    session_result = await db.execute(
        select(SearchSession).where(SearchSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "completed":
        raise HTTPException(status_code=400, detail="Search not completed")

    if session.search_mode == "single":
        results = await db.execute(
            select(SingleTALE)
            .where(SingleTALE.session_id == session_id)
            .order_by(SingleTALE.start)
        )
        tales = results.scalars().all()

        if format == "fasta":
            content = ""
            for t in tales:
                content += f">{session_id}_{t.id} pos={t.start}-{t.end} strand={t.strand}\n"
                content += f"{t.rvd}\n"
            return HTMLResponse(
                content=content,
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=tales_{session_id}.fasta"},
            )

        data = [
            {
                "Start": t.start,
                "End": t.end,
                "Strand": t.strand,
                "DNA": t.dna_sequence,
                "RVD": t.rvd,
                "Length": t.tale_length,
                "GC%": t.gc_content,
            }
            for t in tales
        ]
    else:
        results = await db.execute(
            select(TALEPair)
            .where(TALEPair.session_id == session_id)
            .order_by(TALEPair.left_start)
        )
        pairs = results.scalars().all()

        if format == "fasta":
            content = ""
            for p in pairs:
                content += f">{session_id}_{p.id}_left pos={p.left_start}-{p.left_end} strand={p.left_strand}\n"
                content += f"{p.left_rvd}\n"
                content += f">{session_id}_{p.id}_right pos={p.right_start}-{p.right_end} strand={p.right_strand}\n"
                content += f"{p.right_rvd}\n"
            return HTMLResponse(
                content=content,
                media_type="text/plain",
                headers={"Content-Disposition": f"attachment; filename=tale_pairs_{session_id}.fasta"},
            )

        data = [
            {
                "Left_Start": p.left_start,
                "Left_End": p.left_end,
                "Left_Strand": p.left_strand,
                "Left_DNA": p.left_dna,
                "Left_RVD": p.left_rvd,
                "Right_Start": p.right_start,
                "Right_End": p.right_end,
                "Right_Strand": p.right_strand,
                "Right_DNA": p.right_dna,
                "Right_RVD": p.right_rvd,
                "Spacer_Length": p.spacer_length,
                "Orientation": p.orientation,
            }
            for p in pairs
        ]

    if not data:
        raise HTTPException(status_code=404, detail="No results found")

    df = pd.DataFrame(data)
    output = StringIO()

    if format == "tsv":
        df.to_csv(output, sep="\t", index=False)
        media_type = "text/tab-separated-values"
        filename = f"tale_results_{session_id}.tsv"
    else:
        df.to_csv(output, index=False)
        media_type = "text/csv"
        filename = f"tale_results_{session_id}.csv"

    return HTMLResponse(
        content=output.getvalue(),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/ncbi/search")
async def api_ncbi_search(
    query: str,
    organism: str = "",
):
    """Search NCBI for genes"""
    try:
        results = await search_ncbi_genes(query, organism)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
