import app.tasks.cleanup as _cleanup  # noqa: F401 — side-effect: registers cleanup_stale_jobs task
import app.tasks.fetch as _fetch  # noqa: F401 — side-effect: registers fetch_source_by_id task
import app.tasks.scoring as _scoring  # noqa: F401 — side-effect: registers score_job task
from app.workers import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Trivial task to prove the worker and broker are wired up."""
    return "pong"


celery_app.conf.beat_schedule = {
    "cleanup-stale-jobs": {
        "task": "cleanup_stale_jobs",
        "schedule": 86400.0,  # daily
    },
}
