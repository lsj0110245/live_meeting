
from typing import Dict

class ProgressService:
    def __init__(self):
        # meeting_id -> percent (int)
        self._progress: Dict[int, int] = {}

    def set_progress(self, meeting_id: int, percent: int):
        self._progress[meeting_id] = percent

    def get_progress(self, meeting_id: int) -> int:
        return self._progress.get(meeting_id, 0)
    
    def clear_progress(self, meeting_id: int):
        if meeting_id in self._progress:
            del self._progress[meeting_id]

progress_service = ProgressService()
