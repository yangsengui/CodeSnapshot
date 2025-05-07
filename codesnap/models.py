from typing import List
from pydantic import BaseModel


class Task(BaseModel):
    id: int
    name: str
    branch: str
    base_branch: str
    description: str = ""
    status: str = "Active"
    created: str
    last_activity: str
    commits: int = 0


class TasksList(BaseModel):
    tasks: List[Task] = []
