from fastapi import APIRouter, HTTPException, Depends, Response
from sqlalchemy import select
from app.database import get_db, DBSession
from app.models import TaskModel
from app.schemas import Task, TaskCreate, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("", response_model=list[TaskModel])
async def get_tasks(db: DBSession = Depends(get_db)):
    stmt = select(TaskModel)
    res = await db.execute(stmt)
    return res.scalars()

@router.get("/{task_id}", response_model=Task)
async def get_task(task_id: int, db: DBSession = Depends(get_db)):
    task = await db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("")
async def create_task(
    task: TaskCreate,
    db: DBSession = Depends(get_db)
) -> Task:
    new_task = TaskModel(
        title=task.title,
        description=task.description
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

@router.put("/{task_id}")
async def update_task(task_id: int, updated: TaskUpdate, db: DBSession = Depends(get_db)) -> Task:
    task = await db.get(TaskModel, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.title = updated.title
    task.description = updated.description
    task.done = updated.done

    await db.commit()
    await db.refresh(task)
    return task

@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    db: DBSession = Depends(get_db)
):
    obj = await db.get(TaskModel, task_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(obj)
    await db.commit()
    return Response(status_code=204)