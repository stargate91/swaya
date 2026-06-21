from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.domains.tasks.schemas import BackgroundTaskRead
from app.domains.tasks import task_manager

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

@router.get("", response_model=List[BackgroundTaskRead])
def list_tasks(limit: int = 50):
    """Retrieves a list of all background tasks (active and historical)."""
    return task_manager.list_tasks(limit=limit)

@router.get("/{task_id}", response_model=BackgroundTaskRead)
def get_task(task_id: int):
    """Retrieves progress and status details for a specific task."""
    status = task_manager.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@router.post("/{task_id}/cancel")
def cancel_task(task_id: int):
    """Requests cancellation of a pending or running background task."""
    cancelled = task_manager.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Task cannot be cancelled (might be finished or not found)")
    return {"status": "cancelled", "task_id": task_id}
