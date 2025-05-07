import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any, Union
from .git import GitOps
from .models import Task, TasksList

class TaskManager:
    def __init__(self) -> None:
        self.git: GitOps = GitOps()
        self.task_prefix: str = "codesnap@task/"
        self.config_dir: str = os.path.join(os.getcwd(), ".codesnap")
        self.tasks_file: str = os.path.join(self.config_dir, "tasks.json")
        self._ensure_config_dir()
    
    def _ensure_config_dir(self) -> None:
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)
        
        # Initialize tasks file if it doesn't exist
        if not os.path.exists(self.tasks_file):
            with open(self.tasks_file, "w") as f:
                json.dump([], f)
    
    def _load_tasks(self) -> List[Dict[str, Any]]:
        try:
            with open(self.tasks_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        with open(self.tasks_file, "w") as f:
            json.dump(tasks, f, indent=4)
    
    def _get_next_id(self, tasks: List[Dict[str, Any]]) -> int:
        if not tasks:
            return 1
        return max(task.get("id", 0) for task in tasks) + 1
    
    def create_task(self, task_name: str, description: str = "", force: bool = False, base_branch: Optional[str] = None) -> Tuple[bool, str]:
        if not self.git.is_git_repo():
            return False, "Not in a Git repository"
        
        # Check if there are uncommitted changes and force wasn't specified
        if not force and self.git.get_changes():
            return False, "You have uncommitted changes. Use --force to proceed anyway"
        
        # Get the base branch
        if not base_branch:
            base_branch = self.git.get_current_branch()
            if not base_branch:
                return False, "Unable to determine current branch"
        
        # Check if base branch exists
        success, _ = self.git._run_command(f"git rev-parse --verify {base_branch}")
        if not success:
            return False, f"Base branch '{base_branch}' does not exist"
        
        # Create branch name
        branch_name = f"{self.task_prefix}{task_name}"
        
        # Make sure we're on the base branch first
        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to checkout base branch: {output}"
        
        # Create and checkout the new branch
        success, output = self.git.create_branch(branch_name)
        if not success:
            return False, f"Failed to create task branch: {output}"
        
        # Save task information
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tasks = self._load_tasks()
        task_id = self._get_next_id(tasks)
        
        new_task = Task(
            id=task_id,
            name=task_name,
            branch=branch_name,
            base_branch=base_branch,
            description=description,
            status="Active",
            created=now,
            last_activity=now,
            commits=0
        )
        
        tasks.append(new_task.model_dump())
        self._save_tasks(tasks)
        
        return True, f"Created task branch '{branch_name}'\nDescription: {description or 'None'}\nCreated: {now}"
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        if not self.git.is_git_repo():
            return []
        
        tasks_data = self._load_tasks()
        result = []
        
        for task_data in tasks_data:
            # Create a Task model from the data
            task = Task.model_validate(task_data)
            
            # Format task for display
            result.append({
                "id": task.id,
                "name": task.name,
                "status": task.status,
                "created": task.created,
                "last_activity": task.last_activity,
                "commits": task.commits,
                "description": task.description or "No description"
            })
        
        return result
    
    def get_current_task(self) -> Optional[Task]:
        current_branch = self.git.get_current_branch()
        if not current_branch or self.task_prefix not in current_branch:
            return None
        
        tasks = self._load_tasks()
        for task_data in tasks:
            if task_data["branch"] == current_branch:
                return Task.model_validate(task_data)
        
        return None
    
    def update_task_status(self, task_name: str, status: str, increment_commits: bool = False) -> bool:
        tasks = self._load_tasks()
        updated = False
        
        for task in tasks:
            if task["name"] == task_name:
                task["status"] = status
                task["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if increment_commits:
                    task["commits"] += 1
                updated = True
                break
        
        if updated:
            self._save_tasks(tasks)
            return True
        
        return False
    
    def apply_changes(self, return_to_task: bool = True) -> Tuple[bool, str]:
        task = self.get_current_task()
        if not task:
            return False, "Not on a task branch"
        
        # Get the base branch
        base_branch = task.base_branch
        
        # Save current branch name
        current_branch = self.git.get_current_branch()
        
        # Checkout the base branch
        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to checkout base branch: {output}"
        
        # Merge without committing
        success, output = self.git._run_command(f"git merge --no-commit --no-ff {current_branch}")
        if not success:
            # In case of merge conflict, abort the merge
            self.git._run_command("git merge --abort")
            # Go back to the task branch
            self.git.checkout_branch(current_branch)
            return False, f"Failed to merge changes: {output}"
        
        # Return to the task branch if requested
        if return_to_task:
            self.git.checkout_branch(current_branch)
            return True, f"Applied changes from '{current_branch}' to '{base_branch}' (not committed)"
        else:
            return True, f"Applied changes from '{current_branch}' to '{base_branch}' (not committed) and stayed on {base_branch}"
    
    def merge_changes(self, commit: bool = False, message: Optional[str] = None, squash: bool = False) -> Tuple[bool, str]:
        task = self.get_current_task()
        if not task:
            return False, "Not on a task branch"
        
        # Get the base branch
        base_branch = task.base_branch
        current_branch = self.git.get_current_branch()
        
        if squash:
            # Use commit message or generate default
            if not message:
                message = f"Merge task '{task.name}'"
            
            # Squash and merge
            success, result = self.git.squash_commits(message)
            if success:
                # Update task status
                self.update_task_status(task.name, "Merged", False)
                
                # Switch to base branch
                self.git.checkout_branch(base_branch)
                
                return True, f"Squashed and merged '{current_branch}' into '{base_branch}' and switched to {base_branch}"
            else:
                return False, result
        elif commit:
            # Checkout the base branch
            success, output = self.git.checkout_branch(base_branch)
            if not success:
                return False, f"Failed to checkout base branch: {output}"
            
            # Regular merge with commit
            merge_message = message or f"Merge task '{task.name}'"
            success, output = self.git._run_command(f'git merge --no-ff {current_branch} -m "{merge_message}"')
            
            if success:
                # Update task status
                self.update_task_status(task.name, "Merged", False)
                return True, f"Merged '{current_branch}' into '{base_branch}' and stayed on {base_branch}"
            else:
                # Return to the task branch on failure
                self.git.checkout_branch(current_branch)
                return False, f"Failed to merge: {output}"
        else:
            # Apply changes without committing, but stay on base branch
            return self.apply_changes(return_to_task=False)
    
    def abort_task(self, delete_branch: bool = False) -> Tuple[bool, str]:
        task = self.get_current_task()
        if not task:
            return False, "Not on a task branch"
        
        # Get task name and base branch before aborting
        task_name = task.name
        base_branch = task.base_branch
        task_branch = task.branch
        
        # Abort any changes
        success, message = self.git.abort_changes()
        if not success:
            return False, message
        
        # Switch back to base branch
        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to switch back to {base_branch}: {output}"
        
        # Update task status
        self.update_task_status(task_name, "Aborted", False)
        
        # Delete branch if requested
        if delete_branch:
            success, output = self.git.delete_branch(task_branch)
            if success:
                # Remove task from list
                tasks = self._load_tasks()
                tasks = [t for t in tasks if t['branch'] != task_branch]
                self._save_tasks(tasks)
                return True, f"Abandoned and deleted task '{task_name}'"
            else:
                return False, f"Failed to delete branch: {output}"
        
        return True, f"Abandoned all changes in task '{task_name}' and switched to {base_branch}"
    
    def prune_tasks(self, days: int = 30, merged_only: bool = False) -> int:
        if not self.git.is_git_repo():
            return 0
        
        tasks = self._load_tasks()
        current_time = datetime.now()
        tasks_to_delete = []
        current_branch = self.git.get_current_branch()
        
        for task in tasks:
            # Skip if we're currently on this task branch
            if task["branch"] == current_branch:
                continue
            
            # Check if the task is old enough
            last_activity = datetime.strptime(task["last_activity"], "%Y-%m-%d %H:%M:%S")
            days_old = (current_time - last_activity).days
            
            if days_old >= days:
                # Check if task is merged if merged_only is True
                if merged_only and task["status"] != "Merged":
                    continue
                
                # Check if branch still exists
                success, _ = self.git._run_command(f"git rev-parse --verify {task['branch']}")
                if success:
                    # Delete the branch
                    success, _ = self.git.delete_branch(task["branch"])
                    if success:
                        tasks_to_delete.append(task)
        
        # Remove deleted tasks from the list
        if tasks_to_delete:
            tasks = [task for task in tasks if task not in tasks_to_delete]
            self._save_tasks(tasks)
        
        return len(tasks_to_delete)
