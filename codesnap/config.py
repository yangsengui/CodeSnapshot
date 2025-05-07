import os
import json
from typing import List, Dict, Any

class ConfigOptions:
    def __init__(self) -> None:
        self.task_prefix: str = "codesnap@task/"
        self.config_dir: str = os.path.join(os.getcwd(), ".codesnap")
        self.tasks_file: str = os.path.join(self.config_dir, "tasks.json")
        self.ensure_config_dir()
    
    def ensure_config_dir(self) -> None:
        """Ensure configuration directory and tasks file exist, creating them if they don't."""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
        
        # Initialize tasks file if it doesn't exist
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, "w") as f:
                json.dump([], f)
    
    def load_tasks(self) -> List[Dict[str, Any]]:
        """Load task data from the tasks file.
        
        Returns:
            List[Dict[str, Any]]: List of task data, where each task is a dictionary
        """
        try:
            with open(self.tasks_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def save_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """Save task data to the tasks file.
        
        Args:
            tasks (List[Dict[str, Any]]): List of task data to save
        """
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=4)
