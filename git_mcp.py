import logging
import os
import subprocess
import traceback
from pathlib import Path
from typing import Optional, List

from mcp.server.fastmcp import FastMCP
from mcp.server.stdio import stdio_server

from codesnap.task import TaskManager
from codesnap.git import GitOps

mcp = FastMCP("mcp-codesnap")

repository_path: Optional[Path] = None
task_manager: Optional[TaskManager] = None
git_ops: Optional[GitOps] = None


@mcp.tool()
def task_list_all() -> str:
    """Lists all tasks in the repository.
    
    Returns a formatted table of tasks with their ID, name, status, creation date,
    last activity timestamp, commit count, and description.
    
    Returns:
        str: Formatted list of tasks or a message if no tasks are found.
    """
    global task_manager
    tasks = task_manager.list_tasks()
    if not tasks:
        return "No tasks found."

    task_list = ["Tasks:", "ID | NAME | STATUS | CREATED | LAST ACTIVITY | COMMITS | DESCRIPTION",
                 "---+------+--------+---------+--------------+---------+------------"]

    for task in tasks:
        task_list.append(
            f"{task['id']} | {task['name']} | {task['status']} | {task['created']} | {task['last_activity']} | {task['commits']} | {task['description']}")

    return "\n".join(task_list)


@mcp.tool()
def task_create(task_name: str, description: str = "", force: bool = False,
             base_branch: Optional[str] = None) -> str:
    """Creates a new task branch and switches to it.
    
    Creates a new branch with the task prefix and registers it in the task management system.
    By default, the current branch is used as the base branch unless specified otherwise.
    
    Args:
        task_name: Name for the new task (will be prefixed with task prefix)
        description: Optional description of the task (defaults to empty string)
        force: Whether to proceed if there are uncommitted changes (defaults to False)
        base_branch: Base branch to branch from (defaults to current branch)
    
    Returns:
        str: Success or error message with details about the operation
    """
    global task_manager
    success, message = task_manager.create_task(
        task_name,
        description,
        force,
        base_branch
    )
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_merge(commit: bool = False, message: Optional[str] = None, squash: bool = False) -> str:
    """Merges task changes to the main branch.
    
    Integrates changes from the current task branch into its base branch.
    Can perform a standard merge, commit the merge, or squash all task commits
    into a single commit before merging.
    
    Args:
        commit: Whether to commit the merge (defaults to False)
        message: Optional custom commit message (defaults to auto-generated message)
        squash: Whether to squash all task commits into one (defaults to False)
    
    Returns:
        str: Success or error message with details about the operation
    """
    global task_manager
    success, message = task_manager.merge_changes(
        commit,
        message,
        squash
    )
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_apply(return_to_task: bool = True) -> str:
    """Applies task changes to the main branch without committing.
    
    Temporarily applies the changes from the current task branch to the base branch
    without creating a commit. This allows testing changes on the base branch
    before fully merging.
    
    Args:
        return_to_task: Whether to return to the task branch after applying
                        changes (defaults to True)
    
    Returns:
        str: Success or error message with details about the operation
    """
    global task_manager
    success, message = task_manager.apply_changes(return_to_task)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_abort(delete_branch: bool = False) -> str:
    """Abandons all changes and returns to base branch.
    
    Resets all changes in the current task branch, switches back to the base branch,
    and marks the task as aborted. Optionally deletes the task branch entirely.
    
    Args:
        delete_branch: Whether to delete the task branch after abandoning
                       (defaults to False)
    
    Returns:
        str: Success or error message with details about the operation
    """
    global task_manager
    success, message = task_manager.abort_task(delete_branch)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_prune(days: int = 30, merged_only: bool = False) -> str:
    """Cleans up old task branches based on inactivity period.
    
    Removes task branches that have been inactive for the specified number of days.
    Can be restricted to only delete branches that have already been merged.
    
    Args:
        days: Number of days of inactivity before a branch is eligible for deletion
              (defaults to 30)
        merged_only: Whether to only delete branches that have been merged
                     (defaults to False)
    
    Returns:
        str: Success or info message with number of branches deleted
    """
    global task_manager
    count = task_manager.prune_tasks(days, merged_only)
    if count > 0:
        return f"[SUCCESS] Cleaned up {count} task branch(es) older than {days} days"
    else:
        return f"[INFO] No branches were deleted"


@mcp.tool()
def task_log(show_graph: bool = False) -> str:
    """Shows the commit log of the task branch relative to the main branch.
    
    Displays the commit history that is unique to the current task branch.
    Can optionally show a graphical representation of the commit history.
    
    Args:
        show_graph: Whether to display a graphical representation of the commit
                    history (defaults to False)
    
    Returns:
        str: Formatted commit log or error message
    """
    global git_ops
    log_entries = git_ops.get_task_log(show_graph)
    return "Commit Log:\n" + "\n".join(log_entries)


@mcp.tool()
def git_status() -> str:
    """Shows working tree status of the repository.
    
    Reports the state of the working directory and staging area,
    showing which files have been modified, staged, or are untracked.
    
    Returns:
        str: Current status of the working directory or a message if no changes
    """
    global git_ops
    status = git_ops.get_changes()
    if status:
        return f"Working directory status:\n{status}"
    else:
        return "Working directory clean."


@mcp.tool()
def git_diff() -> str:
    """Shows changes between task and main branch.
    
    Displays the differences between the current task branch and its base branch,
    showing file modifications, additions, and deletions.
    
    Returns:
        str: Diff output or error message
    """
    global git_ops
    diff = git_ops.get_diff()
    return f"Diff with main branch:\n{diff}"


@mcp.tool()
def git_commit(message: str) -> str:
    """Commits changes to current task branch.
    
    Records all current changes in the task branch with the specified commit message.
    Only works when on a task branch, not on main branches.
    
    Args:
        message: Commit message describing the changes
    
    Returns:
        str: Success or error message with commit details
    """
    global git_ops
    success, result_message = git_ops.commit_changes(message)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {result_message}"


@mcp.tool()
def git_init(branch_name: str = "master") -> str:
    """Initializes a new Git repository in the current directory.
    
    Creates a new Git repository with an initial commit and the specified
    main branch name. Creates a .gitignore file if one doesn't exist.
    
    Args:
        branch_name: Name for the main branch (defaults to "master")
    
    Returns:
        str: Success or error message about the repository initialization
    """
    global git_ops
    success = git_ops.initialize_repository(branch_name)
    if success:
        return f"[SUCCESS] Created Git repository with {branch_name} branch"
    else:
        return "[ERROR] Failed to initialize repository"


def setup_manager() -> None:
    import sys

    repository = r"C:\Users\yangsg\PycharmProjects\202505\CodeSnap"

    global repository_path, task_manager, git_ops

    if repository is not None:
        try:
            repository_path = repository
        except Exception as e:
            sys.stderr.write(f"Error initializing repository: {str(e)}")
            return
    else:
        repository_path = Path(os.getcwd())

    # 切换到仓库目录
    original_dir = os.getcwd()
    os.chdir(str(repository_path))

    try:
        task_manager = TaskManager()
        git_ops = GitOps()
    except Exception as e:
        sys.stderr.write(f"Error initializing services: {str(e)}")
        os.chdir(original_dir)
        return


async def serve() -> None:
    logger = logging.getLogger(__name__)
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(read_stream, write_stream, raise_exceptions=True)

setup_manager()

if __name__ == "__main__":
    import asyncio
    import argparse

    logging.basicConfig(level=logging.INFO)

    asyncio.run(serve())
