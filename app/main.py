"""Main FastAPI application"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import Optional
import pandas as pd
from io import StringIO

from app.database import init_db, close_db, get_db
from app.models import SearchSession, TALEPair, generate_session_id
from app.schemas import (
    SearchRequest,
    SearchInitResponse,
    SearchSessionResponse,
    PaginatedResponse,
    TALEPairResponse,
)
from app.tasks import process_search_task, cleanup_old_sessions
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
    # Startup
    await init_db()
    logger.info("Database initialized successfully")

    # Schedule cleanup task (daily at 2 AM)
    from app.database import async_session_maker

    async def cleanup_job():
        async with async_session_maker() as db:
            await cleanup_old_sessions(db)

    scheduler.add_job(cleanup_job, "cron", hour=2, minute=0)
    scheduler.start()
    logger.info("Cleanup scheduler started - runs daily at 2:00 AM")

    yield

    # Shutdown
    scheduler.shutdown()
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="TALE Pair Finder",
    description="Fast and efficient TALE-TALEN pair discovery tool",
    version="2.0.0",
    lifespan=lifespan,
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve main page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    """Serve about page"""
    return templates.TemplateResponse("about.html", {"request": request})


@app.post("/api/search", response_model=SearchInitResponse)
async def initiate_search(
    search_request: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate a TALE pair search.
    Search runs in background, returns session_id immediately.
    """
    # Create search session
    session_id = generate_session_id()

    search_session = SearchSession(
        session_id=session_id,
        status="pending",
        sequence_length=len(search_request.dna_sequence),
    )

    db.add(search_session)
    await db.commit()
    await db.refresh(search_session)

    # Start background search task
    # Note: process_search_task creates its own DB session to avoid concurrency issues
    background_tasks.add_task(
        process_search_task,
        session_id=session_id,
        sequence=search_request.dna_sequence,
        min_tale_length=search_request.min_tale_length,
        max_tale_length=search_request.max_tale_length,
        min_spacer_length=search_request.min_spacer_length,
        max_spacer_length=search_request.max_spacer_length,
        g_code=search_request.g_code,
        position=search_request.position,
        position_range=search_request.position_range,
    )

    return SearchInitResponse(
        session_id=session_id,
        message="Search initiated successfully",
        status="pending",
    )


@app.get("/api/status/{session_id}", response_model=SearchSessionResponse)
async def get_search_status(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get status of a search session"""
    result = await db.execute(select(SearchSession).where(SearchSession.session_id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@app.get("/api/results/{session_id}", response_model=PaginatedResponse)
async def get_results(
    session_id: str,
    page: int = 1,
    per_page: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated TALE pair results for a session.
    Server-side pagination for efficiency.
    """
    # Verify session exists
    session_result = await db.execute(
        select(SearchSession).where(SearchSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get total count
    count_result = await db.execute(
        select(func.count(TALEPair.id)).where(TALEPair.session_id == session_id)
    )
    total = count_result.scalar()

    # Get paginated results
    offset = (page - 1) * per_page
    pairs_result = await db.execute(
        select(TALEPair)
        .where(TALEPair.session_id == session_id)
        .order_by(TALEPair.start)
        .offset(offset)
        .limit(per_page)
    )
    pairs = pairs_result.scalars().all()

    total_pages = (total + per_page - 1) // per_page

    return PaginatedResponse(
        session_id=session_id,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        pairs=[TALEPairResponse.model_validate(pair) for pair in pairs],
    )


@app.get("/api/export/{session_id}")
async def export_results(
    session_id: str,
    format: str = "csv",
    db: AsyncSession = Depends(get_db),
):
    """
    Export all results for a session as CSV or TSV.
    """
    # Verify session exists
    session_result = await db.execute(
        select(SearchSession).where(SearchSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "completed":
        raise HTTPException(status_code=400, detail="Search not completed yet")

    # Get all results
    pairs_result = await db.execute(
        select(TALEPair)
        .where(TALEPair.session_id == session_id)
        .order_by(TALEPair.start)
    )
    pairs = pairs_result.scalars().all()

    if not pairs:
        raise HTTPException(status_code=404, detail="No results found")

    # Convert to DataFrame
    data = [
        {
            "Start": pair.start,
            "End": pair.end,
            "RVD": pair.rvd,
            "Comp_Start": pair.comp_start,
            "Comp_End": pair.comp_end,
            "Comp_RVD": pair.comp_rvd,
            "Spacer_Length": pair.spacer_length,
            "TALE_Length": pair.tale_length,
            "G_Code": pair.g_code,
        }
        for pair in pairs
    ]

    df = pd.DataFrame(data)

    # Export based on format
    if format == "tsv":
        output = StringIO()
        df.to_csv(output, sep="\t", index=False)
        content = output.getvalue()
        media_type = "text/tab-separated-values"
        filename = f"tale_pairs_{session_id}.tsv"
    else:  # csv
        output = StringIO()
        df.to_csv(output, index=False)
        content = output.getvalue()
        media_type = "text/csv"
        filename = f"tale_pairs_{session_id}.csv"

    return HTMLResponse(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
