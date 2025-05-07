from typing import List
from enum import Enum

from pydantic import BaseModel


class TaskStatus(Enum):
    ACTIVE = "Active"
    MERGED = "Merged"
    ABORTED = "Aborted"


class Task(BaseModel):
    id: int
    name: str
    branch: str
    base_branch: str
    description: str = ""
    status: TaskStatus = TaskStatus.ACTIVE
    created: str
    last_activity: str
    commits: int = 0


class TasksList(BaseModel):
    tasks: List[Task] = []
