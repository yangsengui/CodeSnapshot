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
    """Lists all tasks"""
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
    """Creates a new task branch"""
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
    """Merges task changes to the main branch"""
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
    """Applies task changes to the main branch without committing"""
    global task_manager
    success, message = task_manager.apply_changes(return_to_task)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_abort(delete_branch: bool = False) -> str:
    """Abandons all changes and returns to base branch"""
    global task_manager
    success, message = task_manager.abort_task(delete_branch)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {message}"


@mcp.tool()
def task_prune(days: int = 30, merged_only: bool = False) -> str:
    """Cleans up old task branches"""
    global task_manager
    count = task_manager.prune_tasks(days, merged_only)
    if count > 0:
        return f"[SUCCESS] Cleaned up {count} task branch(es) older than {days} days"
    else:
        return f"[INFO] No branches were deleted"


@mcp.tool()
def task_log(show_graph: bool = False) -> str:
    """Shows the commit log of the task branch"""
    global git_ops
    log_entries = git_ops.get_task_log(show_graph)
    return "Commit Log:\n" + "\n".join(log_entries)


@mcp.tool()
def git_status() -> str:
    """Shows working tree status"""
    global git_ops
    status = git_ops.get_changes()
    if status:
        return f"Working directory status:\n{status}"
    else:
        return "Working directory clean."


@mcp.tool()
def git_diff() -> str:
    """Shows changes between task and main branch"""
    global git_ops
    diff = git_ops.get_diff()
    return f"Diff with main branch:\n{diff}"


@mcp.tool()
def git_commit(message: str) -> str:
    """Commits changes to current task branch"""
    global git_ops
    success, result_message = git_ops.commit_changes(message)
    status = "SUCCESS" if success else "ERROR"
    return f"[{status}] {result_message}"


@mcp.tool()
def git_init(branch_name: str = "master") -> str:
    """Initializes a new Git repository"""
    global git_ops
    success = git_ops.initialize_repository(branch_name)
    if success:
        return f"[SUCCESS] Created Git repository with {branch_name} branch"
    else:
        return "[ERROR] Failed to initialize repository"


async def serve(repository: Path | None = None) -> None:
    logger = logging.getLogger(__name__)
    global repository_path, task_manager, git_ops

    if repository is not None:
        try:
            repository_path = repository
            logger.info(f"Using repository at {repository}")
        except Exception as e:
            logger.error(f"Error initializing repository: {str(e)}")
            return
    else:
        # 默认使用当前目录
        repository_path = Path(os.getcwd())
        logger.info(f"Using current directory as repository: {repository_path}")
        
    # 切换到仓库目录
    original_dir = os.getcwd()
    os.chdir(str(repository_path))
    
    # 初始化全局变量
    try:
        task_manager = TaskManager()
        git_ops = GitOps()
        logger.info("Initialized task manager and git operations")
    except Exception as e:
        logger.error(f"Error initializing services: {str(e)}")
        os.chdir(original_dir)
        return

    try:
        async with stdio_server() as (read_stream, write_stream):
            await mcp.run(read_stream, write_stream, raise_exceptions=True)
    finally:
        # 恢复目录
        os.chdir(original_dir)


if __name__ == "__main__":
    import asyncio
    import argparse

    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser(description="CodeSnap MCP Server")
    parser.add_argument("repo_path", nargs="?", type=Path, help="Repository path (defaults to current directory)")
    args = parser.parse_args()

    asyncio.run(serve(args.repo_path))
