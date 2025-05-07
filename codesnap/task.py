from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any

from .git import GitOps
from .models import Task, TaskStatus
from .config import ConfigOptions


class TaskManager:
    def __init__(self) -> None:
        self.config = ConfigOptions()
        self.git: GitOps = GitOps()
    
    def _load_tasks(self) -> List[Dict[str, Any]]:
        return self.config.load_tasks()
    
    def _save_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        self.config.save_tasks(tasks)

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

        success, _ = self.git._run_command(f"git rev-parse --verify {base_branch}")
        if not success:
            return False, f"Base branch '{base_branch}' does not exist"

        branch_name = f"{self.config.task_prefix}{task_name}"

        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to checkout base branch: {output}"

        success, output = self.git.create_branch(branch_name)
        if not success:
            return False, f"Failed to create task branch: {output}"

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tasks = self._load_tasks()
        task_id = self._get_next_id(tasks)
        
        new_task = Task(
            id=task_id,
            name=task_name,
            branch=branch_name,
            base_branch=base_branch,
            description=description,
            status=TaskStatus.ACTIVE,
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
            task = Task.model_validate(task_data)

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
        if not current_branch or self.config.task_prefix not in current_branch:
            return None
        
        tasks = self._load_tasks()
        for task_data in tasks:
            if task_data["branch"] == current_branch:
                return Task.model_validate(task_data)
        
        return None
    
    def update_task_status(self, task_name: str, status: TaskStatus, increment_commits: bool = False) -> bool:
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

        base_branch = task.base_branch

        current_branch = self.git.get_current_branch()

        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to checkout base branch: {output}"

        success, output = self.git._run_command(f"git merge --no-commit --no-ff {current_branch}")
        if not success:
            self.git._run_command("git merge --abort")
            self.git.checkout_branch(current_branch)
            return False, f"Failed to merge changes: {output}"

        if return_to_task:
            self.git.checkout_branch(current_branch)
            return True, f"Applied changes from '{current_branch}' to '{base_branch}' (not committed)"
        else:
            return True, f"Applied changes from '{current_branch}' to '{base_branch}' (not committed) and stayed on {base_branch}"
    
    def merge_changes(self, commit: bool = False, message: Optional[str] = None, squash: bool = False) -> Tuple[bool, str]:
        task = self.get_current_task()
        if not task:
            return False, "Not on a task branch"

        base_branch = task.base_branch
        current_branch = self.git.get_current_branch()
        
        if squash:
            if not message:
                message = f"Merge task '{task.name}'"

            success, result = self.git.squash_commits(message)
            if success:
                self.update_task_status(task.name, TaskStatus.MERGED, False)
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
                self.update_task_status(task.name, TaskStatus.MERGED, False)
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
        self.update_task_status(task_name, TaskStatus.ABORTED, False)
        
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
                if merged_only and task["status"] != TaskStatus.MERGED.value:
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
