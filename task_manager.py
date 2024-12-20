from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import logging
from collections import deque
from dataclasses import dataclass
import uuid
from websocket_manager import websocket_manager
from functools import partial
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class Task:
    """Represents a task in the queue."""
    id: str
    type: str
    user_id: str
    status: str
    created_at: datetime
    data: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TaskQueue:
    """Thread-safe queue for managing tasks."""
    def __init__(self):
        self._queue = deque()
        self._processing = {}
        self._results = {}
        self._lock = asyncio.Lock()
    
    async def enqueue(self, task: Task) -> str:
        """Add a task to the queue."""
        async with self._lock:
            self._queue.append(task)
            return task.id
    
    async def dequeue(self) -> Optional[Task]:
        """Get next task from the queue."""
        async with self._lock:
            return self._queue.popleft() if self._queue else None
    
    async def mark_processing(self, task_id: str, task: Task):
        """Mark a task as being processed."""
        async with self._lock:
            self._processing[task_id] = task
    
    async def mark_complete(self, task_id: str, result: Dict[str, Any]):
        """Mark a task as complete with its result."""
        async with self._lock:
            if task_id in self._processing:
                task = self._processing.pop(task_id)
                task.status = "completed"
                task.result = result
                self._results[task_id] = task
                
                # Send WebSocket update
                await websocket_manager.broadcast_to_user(
                    task.user_id,
                    {
                        "type": "task_complete",
                        "task_id": task_id,
                        "result": result
                    }
                )
    
    async def mark_failed(self, task_id: str, error: str):
        """Mark a task as failed with error message."""
        async with self._lock:
            if task_id in self._processing:
                task = self._processing.pop(task_id)
                task.status = "failed"
                task.error = error
                self._results[task_id] = task
                
                # Send WebSocket update
                await websocket_manager.broadcast_to_user(
                    task.user_id,
                    {
                        "type": "task_failed",
                        "task_id": task_id,
                        "error": error
                    }
                )
    
    async def get_task_status(self, task_id: str) -> Optional[Task]:
        """Get the current status of a task."""
        async with self._lock:
            if task_id in self._results:
                return self._results[task_id]
            if task_id in self._processing:
                return self._processing[task_id]
            for task in self._queue:
                if task.id == task_id:
                    return task
            return None

class TaskManager:
    """Manages task queues and processing."""
    def __init__(self):
        self.queues: Dict[str, TaskQueue] = {
            "pack_opening": TaskQueue()
        }
        self._running = False
        self._workers = {}
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
    
    async def start(self):
        """Start the task manager."""
        if self._running:
            return
        
        self._running = True
        for queue_name in self.queues:
            self._workers[queue_name] = asyncio.create_task(
                self._process_queue(queue_name)
            )
    
    async def stop(self):
        """Stop the task manager."""
        self._running = False
        for worker in self._workers.values():
            worker.cancel()
        self._workers.clear()
        self._thread_pool.shutdown(wait=True)
    
    async def submit_task(
        self,
        queue_name: str,
        task_type: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> str:
        """Submit a new task to a queue."""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        
        task = Task(
            id=str(uuid.uuid4()),
            type=task_type,
            user_id=user_id,
            status="pending",
            created_at=datetime.utcnow(),
            data=data
        )
        
        await self.queues[queue_name].enqueue(task)
        
        # Send WebSocket update for task submission
        await websocket_manager.broadcast_to_user(
            user_id,
            {
                "type": "task_submitted",
                "task_id": task.id,
                "task_type": task_type
            }
        )
        
        return task.id
    
    async def get_task_status(self, queue_name: str, task_id: str) -> Optional[Task]:
        """Get the status of a task."""
        if queue_name not in self.queues:
            raise ValueError(f"Unknown queue: {queue_name}")
        
        return await self.queues[queue_name].get_task_status(task_id)
    
    async def _process_queue(self, queue_name: str):
        """Process tasks in a queue."""
        queue = self.queues[queue_name]
        
        while self._running:
            try:
                task = await queue.dequeue()
                if not task:
                    await asyncio.sleep(0.1)  # Prevent busy waiting
                    continue
                
                await queue.mark_processing(task.id, task)
                
                try:
                    if task.type == "open_pack":
                        from pack_handler import process_pack_opening
                        # Run synchronous function in thread pool
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(
                            self._thread_pool,
                            partial(process_pack_opening, task.user_id, task.data)
                        )
                        
                        # Send credit update notification
                        from user_models import UserModel
                        from database import SessionLocal
                        db = SessionLocal()
                        try:
                            user = db.query(UserModel).filter(UserModel.firebase_id == task.user_id).first()
                            if user:
                                await user.notify_credit_update(
                                    -result["cost"],
                                    "Opened a booster pack",
                                    "pack_opening"
                                )
                        finally:
                            db.close()
                        
                        await queue.mark_complete(task.id, result)
                    else:
                        await queue.mark_failed(
                            task.id,
                            f"Unknown task type: {task.type}"
                        )
                
                except Exception as e:
                    logger.error(f"Error processing task {task.id}: {e}")
                    await queue.mark_failed(task.id, str(e))
            
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(1)  # Prevent rapid retries on persistent errors

# Global task manager instance
task_manager = TaskManager()
