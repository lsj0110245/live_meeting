from datetime import datetime
from pydantic import BaseModel

class FolderBase(BaseModel):
    name: str

class FolderCreate(FolderBase):
    pass

class FolderUpdate(FolderBase):
    pass

class Folder(FolderBase):
    id: int
    owner_id: int
    created_at: datetime

    class Config:
        from_attributes = True
