"""Background worker that processes WebAPT tasks sequentially."""

import threading
import time
import sys
import os
from pathlib import Path

# Allow importing webapt from parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import (
    get_next_queued_task, set_task_running, set_task_done,
    set_task_failed, get_queue, recompute_queue_positions,
)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()
_current_task_id: int | None = None
_lock = threading.Lock()

# SSE subscribers: list of queue.Queue instances
_sse_subscribers: list = []
_sse_lock = threading.Lock()


def get_current_task_id() -> int | None:
    return _current_task_id


def subscribe_sse():
    import queue
    q = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_subscribers.append(q)
    return q


def unsubscribe_sse(q):
    with _sse_lock:
        try:
            _sse_subscribers.remove(q)
        except ValueError:
            pass


def broadcast_update(event_type: str, data: dict):
    import json
    payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_subscribers:
            try:
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_subscribers.remove(q)


def _run_webapt_task(task: dict) -> tuple[str, str]:
    """Execute a WebAPT task. Returns (summary, output_dir)."""
    try:
        from webapt.config import WebAPTConfig
        from webapt.orchestrator import (
            run_full_pipeline,
            run_accessibility_only,
            run_analysis_only,
        )

        config = WebAPTConfig.from_env(project_name=task["project_name"])
        config.ensure_dirs()

        # Use the full unified task_input (stored in extra_task) as the user message.
        # Fall back to legacy URL-based construction for older tasks.
        if task.get("extra_task"):
            user_message = task["extra_task"]
        else:
            user_message = f"Analyze {task['target_url']}"

        task_type = task["task_type"]  # 'accessibility', 'analysis', or 'full'

        if task_type == "accessibility":
            summary = run_accessibility_only(user_message, config)[:500]
        elif task_type == "analysis":
            summary = run_analysis_only(user_message, config)[:500]
        else:  # 'full' (includes legacy tasks and 'both' mapped to 'full')
            summary = run_full_pipeline(user_message, config)[:500]

        return summary, str(config.project_dir)

    except ImportError as e:
        # webapt not installed — run in simulation mode for UI testing
        import time as t
        t.sleep(8)
        sim_dir = f"./outputs/{task['project_name']}"
        return f"[SIMULATION] Task completed for {task['target_url']}", sim_dir

    except Exception as e:
        raise RuntimeError(str(e)) from e


def _worker_loop():
    global _current_task_id
    print("[Worker] Started background task worker.")

    while not _stop_event.is_set():
        task = get_next_queued_task()

        if task is None:
            time.sleep(2)
            continue

        task_id = task["id"]

        with _lock:
            _current_task_id = task_id

        set_task_running(task_id)
        task_label = task.get("target_url") or (task.get("extra_task", "")[:60] + "...")
        broadcast_update("task_started", {
            "task_id": task_id,
            "task_type": task["task_type"],
            "target_url": task_label,
        })

        print(f"[Worker] Running task #{task_id}: {task['task_type']} → {task_label}")

        try:
            summary, output_dir = _run_webapt_task(task)
            set_task_done(task_id, summary, output_dir)
            broadcast_update("task_done", {
                "task_id": task_id,
                "summary": summary,
                "output_dir": output_dir,
            })
            print(f"[Worker] Task #{task_id} completed.")
        except Exception as e:
            error = str(e)
            set_task_failed(task_id, error)
            broadcast_update("task_failed", {"task_id": task_id, "error": error})
            print(f"[Worker] Task #{task_id} failed: {error}")

        with _lock:
            _current_task_id = None

        recompute_queue_positions()
        broadcast_update("queue_updated", {"queue": get_queue()})
        time.sleep(1)

    print("[Worker] Worker stopped.")


def start_worker():
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="webapt-worker")
    _worker_thread.start()


def stop_worker():
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5)
