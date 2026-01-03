"""Background tasks for cleanup"""

from datetime import datetime, timedelta
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SearchSession, TALEPair, SingleTALE, SearchCache
from app.config import get_settings
from app.logging_config import get_logger

settings = get_settings()
logger = get_logger(__name__)


async def cleanup_old_sessions(db: AsyncSession):
    """
    Remove search sessions and associated results older than retention period.
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

    # Delete associated single TALEs
    await db.execute(delete(SingleTALE).where(SingleTALE.session_id.in_(old_session_ids)))

    # Delete cache entries
    await db.execute(delete(SearchCache).where(SearchCache.session_id.in_(old_session_ids)))

    # Delete search sessions
    await db.execute(delete(SearchSession).where(SearchSession.session_id.in_(old_session_ids)))

    await db.commit()

    logger.info(f"Cleaned up {len(old_session_ids)} old sessions (retention period: {settings.session_retention_days} days)")
