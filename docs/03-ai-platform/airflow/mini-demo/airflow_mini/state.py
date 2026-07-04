"""State machine constants for Airflow Mini Demo."""

# TaskInstance states
NONE = "none"
SCHEDULED = "scheduled"
QUEUED = "queued"
RUNNING = "running"
SUCCESS = "success"
FAILED = "failed"
SKIPPED = "skipped"
UPSTREAM_FAILED = "upstream_failed"
UP_FOR_RETRY = "up_for_retry"
DEFERRED = "deferred"

# DAG Run states
DR_QUEUED = "queued"
DR_RUNNING = "running"
DR_SUCCESS = "success"
DR_FAILED = "failed"

TERMINAL_TI_STATES = {SUCCESS, FAILED, SKIPPED, UPSTREAM_FAILED}


def is_terminal(state: str) -> bool:
    return state in TERMINAL_TI_STATES
