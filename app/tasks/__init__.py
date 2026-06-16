from app.workers import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    """Trivial task to prove the worker and broker are wired up."""
    return "pong"


# Phase 1+ registers per-source fetch tasks here, scheduled per source cadence, e.g.:
# celery_app.conf.beat_schedule = {
#     "fetch-adzuna": {"task": "fetch_source", "schedule": 3600.0, "args": (adzuna_id,)},
# }
celery_app.conf.beat_schedule = {}
