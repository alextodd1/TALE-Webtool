"""Background tasks for search processing and cleanup"""

import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SearchSession, TALEPair
from app.search import find_tale_pairs
from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def process_search_task(
    session_id: str,
    sequence: str,
    min_tale_length: int,
    max_tale_length: int,
    min_spacer_length: int,
    max_spacer_length: int,
    g_code: str,
    position: int | None,
    position_range: int | None,
):
    """
    Background task to process TALE search.
    Updates search session status and stores results.
    Creates its own database session to avoid concurrency issues.
    """
    # Import here to avoid circular dependency
    from app.database import async_session_maker

    # Create a new database session for this background task
    async with async_session_maker() as db:
        try:
            # Update status to processing
            result = await db.execute(
                select(SearchSession).where(SearchSession.session_id == session_id)
            )
            search_session = result.scalar_one_or_none()

            if not search_session:
                logger.warning(f"Search session not found: {session_id}")
                return

            logger.info(f"Starting search for session {session_id} - sequence length: {len(sequence)} bp")
            search_session.status = "processing"
            search_session.progress = 0
            await db.commit()

            # Get the current event loop to schedule coroutines from the thread
            loop = asyncio.get_event_loop()

            # Progress callback to update in-memory object only
            # We don't commit here to avoid concurrent session operations
            async def update_progress(progress: int):
                search_session.progress = progress

            # Progress callback that works from within a thread
            def progress_callback(progress: int):
                # Schedule the coroutine in the main event loop from the thread
                asyncio.run_coroutine_threadsafe(update_progress(progress), loop)

            # Run search algorithm (CPU-bound, but runs in background)
            pairs = await asyncio.to_thread(
                find_tale_pairs,
                sequence=sequence,
                min_tale_length=min_tale_length,
                max_tale_length=max_tale_length,
                min_spacer_length=min_spacer_length,
                max_spacer_length=max_spacer_length,
                g_code=g_code,
                position=position,
                position_range=position_range,
                progress_callback=progress_callback,
            )

            # Store results in database using bulk insert
            tale_pair_objects = [
                TALEPair(
                    session_id=session_id,
                    start=pair.start,
                    end=pair.end,
                    rvd=pair.rvd,
                    comp_start=pair.comp_start,
                    comp_end=pair.comp_end,
                    comp_rvd=pair.comp_rvd,
                    spacer_length=pair.spacer_length,
                    tale_length=pair.tale_length,
                    g_code=pair.g_code,
                )
                for pair in pairs
            ]

            # Bulk insert for efficiency
            if tale_pair_objects:
                db.add_all(tale_pair_objects)

            # Update session status
            search_session.status = "completed"
            search_session.total_pairs = len(pairs)
            search_session.progress = 100
            search_session.completed_at = datetime.utcnow()

            await db.commit()

            logger.info(f"Search completed for session {session_id} - found {len(pairs)} TALE pairs")

        except Exception as e:
            # Handle errors - rollback any pending transaction first
            await db.rollback()

            logger.error(f"Search failed for session {session_id}: {str(e)}", exc_info=True)

            # Fetch the session again with a fresh query to avoid session state issues
            result = await db.execute(
                select(SearchSession).where(SearchSession.session_id == session_id)
            )
            search_session = result.scalar_one_or_none()

            if search_session:
                search_session.status = "failed"
                search_session.total_pairs = search_session.total_pairs or 0
                search_session.progress = 100
                search_session.error_message = str(e)[:500]
                search_session.completed_at = datetime.utcnow()
                await db.commit()


async def cleanup_old_sessions(db: AsyncSession):
    """
    Remove search sessions and associated TALE pairs older than retention period.
    Runs as scheduled background task.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=settings.session_retention_days)

    logger.info(f"Starting cleanup of sessions older than {cutoff_date}")

    # Get old session IDs
    result = await db.execute(
        select(SearchSession.session_id).where(SearchSession.created_at < cutoff_date)
    )
    old_session_ids = [row[0] for row in result.fetchall()]

    if not old_session_ids:
        logger.info("No old sessions to clean up")
        return

    # Delete associated TALE pairs
    await db.execute(delete(TALEPair).where(TALEPair.session_id.in_(old_session_ids)))

    # Delete search sessions
    await db.execute(delete(SearchSession).where(SearchSession.session_id.in_(old_session_ids)))

    await db.commit()

    logger.info(f"Cleaned up {len(old_session_ids)} old sessions (retention period: {settings.session_retention_days} days)")
