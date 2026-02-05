import asyncio
from typing import Dict, Optional, Coroutine, Any
import logging

logger = logging.getLogger(__name__)

class BackgroundTaskManager:
    """
    백그라운드 작업(STT, 요약 등)을 추적하고 취소할 수 있는 서비스
    """
    def __init__(self):
        # meeting_id: asyncio.Task
        self._tasks: Dict[int, asyncio.Task] = {}

    def add_task(self, meeting_id: int, coro: Coroutine[Any, Any, Any]):
        """
        새로운 백그라운드 작업을 추가합니다. 
        이미 동일한 meeting_id에 작업이 있다면 취소 후 새로 시작합니다.
        """
        self.cancel_task(meeting_id)
        
        task = asyncio.create_task(coro)
        self._tasks[meeting_id] = task
        
        # 작업 완료 시 맵에서 제거
        task.add_done_callback(lambda t: self._remove_task(meeting_id, t))
        logger.info(f"Task added for meeting {meeting_id}")

    def cancel_task(self, meeting_id: int):
        """
        진행 중인 작업을 취소합니다.
        """
        if meeting_id in self._tasks:
            task = self._tasks[meeting_id]
            if not task.done():
                task.cancel()
                logger.info(f"Task cancelled for meeting {meeting_id}")
            del self._tasks[meeting_id]

    def _remove_task(self, meeting_id: int, task: asyncio.Task):
        """
        작업 완료 후 내부 맵에서 안전하게 제거
        """
        if meeting_id in self._tasks and self._tasks[meeting_id] == task:
            del self._tasks[meeting_id]
            # logger.info(f"Task removed from manager for meeting {meeting_id}")

# 싱글톤 인스턴스
task_manager = BackgroundTaskManager()
