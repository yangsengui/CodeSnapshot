#!/usr/bin/env python3
import os
import sys
from typing import Optional, List
import click
from colorama import init, Fore
from datetime import datetime

init(autoreset=True)

# Import operations modules
try:
    from codesnap.git import GitOps
    from codesnap.task import TaskManager
except ImportError:
    # For development
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from codesnap.git import GitOps
    from codesnap.task import TaskManager


# Main CLI group
@click.group(help=f"{Fore.CYAN}CS - CodeSnap{Fore.RESET} - AI-powered code snapshot tool")
def cli() -> None:
    pass


# Initialize repository
@cli.command(help="Initialize a new repository with CodeSnap")
@click.option("--branch", default="master", help="Name of the main branch")
def init(branch: str) -> None:
    git_ops = GitOps()
    success = git_ops.initialize_repository(branch)
    if success:
        click.echo(f"[{Fore.GREEN}SUCCESS{Fore.RESET}] Created Git repository with {branch} branch")
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] Failed to initialize repository")


# Start a new task
@cli.command(help="Create a new task branch")
@click.argument("task_name")
@click.option("--description", "-d", default="", help="Task description")
@click.option("--force", is_flag=True, help="Create task branch with current changes")
@click.option("--branch", help="Base branch (defaults to current branch)")
def start(task_name: str, description: str, force: bool, branch: Optional[str]) -> None:
    task_manager = TaskManager()
    success, message = task_manager.create_task(task_name, description, force, branch)
    if success:
        click.echo(f"[{Fore.GREEN}SUCCESS{Fore.RESET}] {message}")
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {message}")


# Commit changes
@cli.command(help="Commit changes to the current task branch")
@click.argument("message")
def commit(message: str) -> None:
    git_ops = GitOps()
    success, result = git_ops.commit_changes(message)
    if success:
        click.echo(result)
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {result}")


# Apply changes to main branch
@cli.command(help="Apply all changes to the main branch without committing")
def apply() -> None:
    task_manager = TaskManager()
    success, message = task_manager.apply_changes()
    if success:
        click.echo(f"[{Fore.GREEN}INFO{Fore.RESET}] {message}")
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {message}")


# Merge changes to main branch
@cli.command(help="Apply all changes to the main branch")
@click.option("--commit", is_flag=True, help="Commit changes after applying")
@click.option("--message", "-m", help="Commit message")
@click.option("--squash", is_flag=True, help="Squash all commits into one")
def merge(commit: bool, message: Optional[str], squash: bool) -> None:
    task_manager = TaskManager()
    success, result = task_manager.merge_changes(commit, message, squash)
    if success:
        click.echo(f"[{Fore.GREEN}SUCCESS{Fore.RESET}] {result}")
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {result}")


# Abort current task
@cli.command(help="Abandon all changes in the current task")
def abort() -> None:
    task_manager = TaskManager()
    success, message = task_manager.abort_task()
    if success:
        click.echo(f"[{Fore.GREEN}INFO{Fore.RESET}] {message}")
    else:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {message}")


# List all tasks
@cli.command(help="List all task branches")
def list() -> None:
    task_manager = TaskManager()
    tasks = task_manager.list_tasks()

    if not tasks:
        click.echo("No tasks found.")
        return

    # Print table header
    click.echo("ID | NAME | STATUS | CREATED | LAST ACTIVITY | COMMITS | DESCRIPTION")
    click.echo("---+------+--------+---------+--------------+---------+------------")

    # Print tasks
    for task in tasks:
        click.echo(
            f"{task['id']} | {task['name']} | {task['status']} | {task['created']} | {task['last_activity']} | {task['commits']} | {task['description']}")


# View task log
@cli.command(help="View commits in the current task")
@click.option("--graph", is_flag=True, help="Show commit graph")
def log(graph: bool) -> None:
    git_ops = GitOps()
    commits = git_ops.get_task_log(graph)
    for commit in commits:
        click.echo(commit)


# View diff between task and main branch
@cli.command(help="Show differences between task branch and main branch")
def diff() -> None:
    git_ops = GitOps()
    differences = git_ops.get_diff()
    click.echo(differences)


# Prune old task branches
@cli.command(help="Clean up old task branches")
@click.option("--days", type=int, default=30, help="Delete branches older than this many days")
@click.option("--merged", is_flag=True, help="Only delete merged branches")
def prune(days: int, merged: bool) -> None:
    task_manager = TaskManager()
    count = task_manager.prune_tasks(days, merged)
    if count > 0:
        click.echo(f"[{Fore.GREEN}SUCCESS{Fore.RESET}] Cleaned up {count} task branch(es) older than {days} days")
    else:
        click.echo(f"[{Fore.YELLOW}INFO{Fore.RESET}] No branches were deleted")


# Entry point
def main() -> None:
    try:
        cli()
    except Exception as e:
        click.echo(f"[{Fore.RED}ERROR{Fore.RESET}] {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
