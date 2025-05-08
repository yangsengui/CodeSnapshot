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
        """
        Load task list from configuration file.
        
        Returns:
            List[Dict[str, Any]]: List of task data
        """
        return self.config.load_tasks()

    def _save_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """
        Save task list to configuration file.
        
        Args:
            tasks (List[Dict[str, Any]]): List of task data to save
        """
        self.config.save_tasks(tasks)

    def _get_next_id(self, tasks: List[Dict[str, Any]]) -> int:
        """
        Get the next available task ID.
        
        Args:
            tasks (List[Dict[str, Any]]): Current task list
            
        Returns:
            int: Next available task ID
        """
        if not tasks:
            return 1
        return max(task.get("id", 0) for task in tasks) + 1
    
    def create_task(self, task_name: str, description: str = "", force: bool = False, base_branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Create a new task and switch to the task branch.
        
        Args:
            task_name (str): Task name
            description (str): Task description, defaults to empty string
            force (bool): Whether to force creation even if there are uncommitted changes, defaults to False
            base_branch (Optional[str]): Base branch, defaults to current branch
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.git.is_git_repo():
            return False, "Not in a Git repository"

        if not force and self.git.get_changes():
            return False, "You have uncommitted changes. Use --force to proceed anyway"

        if not base_branch:
            base_branch = self.git.get_current_branch()
            if not base_branch:
                return False, "Unable to determine current branch"

        if not self.git.verify_branch_exists(base_branch):
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
        
        # 确保枚举值被转换为字符串
        task_dict = new_task.model_dump()
        task_dict['status'] = task_dict['status'].value
        
        tasks.append(task_dict)
        self._save_tasks(tasks)
        
        return True, f"Created task branch '{branch_name}'\nDescription: {description or 'None'}\nCreated: {now}"
    
    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        Get a list of all tasks.
        
        Returns:
            List[Dict[str, Any]]: List of task information
        """
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
        """
        Get the task corresponding to the current branch.
        
        Returns:
            Optional[Task]: Current task object, or None if not on a task branch
        """
        current_branch = self.git.get_current_branch()
        if not current_branch or self.config.task_prefix not in current_branch:
            return None
        
        tasks = self._load_tasks()
        for task_data in tasks:
            if task_data["branch"] == current_branch:
                return Task.model_validate(task_data)
        
        return None
    
    def update_task_status(self, task_name: str, status: TaskStatus, increment_commits: bool = False) -> bool:
        """
        Update task status.
        
        Args:
            task_name (str): Task name
            status (TaskStatus): New status
            increment_commits (bool): Whether to increment commit count, defaults to False
            
        Returns:
            bool: True if update successful, False otherwise
        """
        tasks = self._load_tasks()
        updated = False
        
        for task in tasks:
            if task["name"] == task_name:
                # 将TaskStatus枚举转换为字符串形式再保存
                task["status"] = status.value if isinstance(status, TaskStatus) else status
                task["last_activity"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                if increment_commits:
                    task["commits"] += 1
                updated = True
                break
        
        if updated:
            self._save_tasks(tasks)
            return True
        
        return False


    def merge_changes(self, commit: bool = False, message: Optional[str] = None, squash: bool = False) -> Tuple[bool, str]:
        """
        Merge task branch changes into the base branch.
        
        Args:
            commit (bool): Whether to commit the merge, defaults to False
            message (Optional[str]): The merge commit message, defaults to None
            squash (bool): Whether to squash commits, defaults to False
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
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
                # 更新任务状态为已合并
                self.update_task_status(task.name, TaskStatus.MERGED, False)
                self.git.checkout_branch(base_branch)
                
                return True, f"Squashed and merged '{current_branch}' into '{base_branch}' and switched to {base_branch}"
            else:
                return False, result
        elif commit:
            success, output = self.git.checkout_branch(base_branch)
            if not success:
                return False, f"Failed to checkout base branch: {output}"

            merge_message = message or f"Merge task '{task.name}'"
            success, output = self.git.merge_with_commit(current_branch, merge_message)
            
            if success:
                self.update_task_status(task.name, TaskStatus.MERGED, False)
                return True, f"Merged '{current_branch}' into '{base_branch}' and stayed on {base_branch}"
            else:
                self.git.checkout_branch(current_branch)
                return False, f"Failed to merge: {output}"
        else:
            return self.apply_changes(return_to_task=False)
    
    def abort_task(self, delete_branch: bool = False) -> Tuple[bool, str]:
        """
        Abandon the task, revert all changes and return to the base branch.
        
        Args:
            delete_branch (bool): Whether to delete the task branch, defaults to False
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        task = self.get_current_task()
        if not task:
            return False, "Not on a task branch"

        task_name = task.name
        base_branch = task.base_branch
        task_branch = task.branch

        success, message = self.git.abort_changes()
        if not success:
            return False, message

        success, output = self.git.checkout_branch(base_branch)
        if not success:
            return False, f"Failed to switch back to {base_branch}: {output}"

        # 将任务状态更新为终止
        self.update_task_status(task_name, TaskStatus.ABORTED, False)

        if delete_branch:
            success, output = self.git.delete_branch(task_branch)
            if success:
                tasks = self._load_tasks()
                tasks = [t for t in tasks if t['branch'] != task_branch]
                self._save_tasks(tasks)
                return True, f"Abandoned and deleted task '{task_name}'"
            else:
                return False, f"Failed to delete branch: {output}"
        
        return True, f"Abandoned all changes in task '{task_name}' and switched to {base_branch}"
    
    def prune_tasks(self, days: int = 30, merged_only: bool = False) -> int:
        """
        Clean up old tasks, remove task branches that have been inactive for a while.
        
        Args:
            days (int): Threshold for days of inactivity, defaults to 30 days
            merged_only (bool): Whether to only clean up merged tasks, defaults to False
            
        Returns:
            int: Number of tasks cleaned up
        """
        if not self.git.is_git_repo():
            return 0
        
        tasks = self._load_tasks()
        current_time = datetime.now()
        tasks_to_delete = []
        current_branch = self.git.get_current_branch()
        
        for task in tasks:
            if task["branch"] == current_branch:
                continue

            last_activity = datetime.strptime(task["last_activity"], "%Y-%m-%d %H:%M:%S")
            days_old = (current_time - last_activity).days
            
            if days_old >= days:
                # 检查任务状态，只删除已合并的任务
                if merged_only and task["status"] != TaskStatus.MERGED.value:
                    continue

                if self.git.verify_branch_exists(task['branch']):
                    success, _ = self.git.delete_branch(task["branch"])
                    if success:
                        tasks_to_delete.append(task)

        if tasks_to_delete:
            tasks = [task for task in tasks if task not in tasks_to_delete]
            self._save_tasks(tasks)
        
        return len(tasks_to_delete)
