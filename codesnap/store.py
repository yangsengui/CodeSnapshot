import os
from pathlib import Path
from typing import Optional

from .task import TaskManager
from .git import GitOps


class GlobalStore:
    def __init__(self):
        self.repository_path: Optional[Path] = None
        self.task_manager: Optional[TaskManager] = None
        self.git_ops: Optional[GitOps] = None
        
    def setup_manager(self, repository_path: Optional[str] = None) -> None:
        """
        Initialize the repository manager and Git operations tool
        
        Args:
            repository_path: Repository path, if None then use the current working directory
        """
        if repository_path is not None:
            self.repository_path = Path(repository_path)
        else:
            self.repository_path = Path(os.getcwd())

        original_dir = os.getcwd()
        os.chdir(str(self.repository_path))

        try:
            self.task_manager = TaskManager()
            self.git_ops = GitOps()
        except Exception as e:
            os.chdir(original_dir)
            raise e


store = GlobalStore()
