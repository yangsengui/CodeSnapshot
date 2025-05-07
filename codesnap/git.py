import os
import subprocess
import re
from datetime import datetime
from typing import Tuple, List, Optional

from .config import ConfigOptions


class GitOps:
    def __init__(self) -> None:
        self.config = ConfigOptions()
    
    def _run_command(self, command: str, capture_output: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Execute a shell command and return the result.
        
        Args:
            command (str): The shell command to execute
            capture_output (bool): Whether to capture the command output
            
        Returns:
            Tuple[bool, Optional[str]]: (success flag, output or error message)
        """
        try:
            if capture_output:
                result = subprocess.run(command, check=True, shell=True, 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        encoding='utf-8')
                return True, result.stdout.strip()
            else:
                subprocess.run(command, check=True, shell=True)
                return True, None
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip() if e.stderr else str(e)
    
    def is_git_repo(self) -> bool:
        """
        Check if the current directory is a Git repository.
        
        Returns:
            bool: True if it's a Git repository, False otherwise
        """
        return self._run_command("git rev-parse --is-inside-work-tree")[0]
    
    def initialize_repository(self, branch_name: str = "master") -> bool:
        """
        Initialize a Git repository and create the initial commit.
        
        Args:
            branch_name (str): The main branch name, defaults to "master"
            
        Returns:
            bool: True if initialization is successful, False otherwise
        """
        if self.is_git_repo():
            return False
        
        success, _ = self._run_command("git init")
        if not success:
            return False

        # Create initial commit
        success, _ = self._run_command("git checkout -b " + branch_name)
        if not success:
            return False
        
        # Create a .gitignore file if it doesn't exist
        if not os.path.exists(".gitignore"):
            with open(".gitignore", "w") as f:
                f.write("# CodeSnap auto-generated .gitignore\n")
        
        # Add all files and create initial commit
        self._run_command("git add .")
        self._run_command('git commit -m "Initial commit"')
        
        return True
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get the name of the current Git branch.
        
        Returns:
            Optional[str]: Current branch name, or None if an error occurs
        """
        success, output = self._run_command("git branch --show-current")
        return output if success else None
    
    def create_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Create and switch to a new branch.
        
        Args:
            branch_name (str): The name of the new branch
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        success, output = self._run_command(f"git checkout -b {branch_name}")
        return success, output
    
    def checkout_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Switch to the specified branch.
        
        Args:
            branch_name (str): The name of the branch to switch to
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        success, output = self._run_command(f"git checkout {branch_name}")
        return success, output
    
    def get_changes(self) -> str:
        """
        Get the change status of the current working directory.
        
        Returns:
            str: A brief description of the working directory status
        """
        success, output = self._run_command("git status --porcelain")
        return output if success else ""
    
    def commit_changes(self, message: str) -> Tuple[bool, str]:
        """
        Commit current changes.
        
        Args:
            message (str): The commit message
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.get_changes():
            return False, "No changes to commit"

        current_branch = self.get_current_branch()
        if self.config.task_prefix in current_branch:
            success, _ = self._run_command("git add .")
            if not success:
                return False, "Failed to stage changes"

            success, output = self._run_command(f'git commit -m "{message}"')
            if not success:
                return False, f"Failed to commit: {output}"

            commit_hash_match = re.search(r'\[.*\s([a-f0-9]+)\]', output)
            commit_hash = commit_hash_match.group(1) if commit_hash_match else "unknown"
            
            return True, f"[{current_branch} {commit_hash}] {message}"
        else:
            return False, "Not on a task branch"
    
    def get_main_branch(self) -> Optional[str]:
        """
        Get the main branch name (master or main).
        
        Returns:
            Optional[str]: The main branch name, or None if not found
        """
        for branch in ["master", "main"]:
            success, _ = self._run_command(f"git rev-parse --verify {branch}")
            if success:
                return branch
        return None
    
    def get_task_log(self, show_graph: bool = False) -> List[str]:
        """
        Get the commit log of the task branch relative to the main branch.
        
        Args:
            show_graph (bool): Whether to display a commit graph, defaults to False
            
        Returns:
            List[str]: List of commit log lines
        """
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return ["Unable to determine branches"]

        graph_option = "--graph --oneline --decorate" if show_graph else "--oneline"
        success, output = self._run_command(f"git log {graph_option} {main_branch}..{current_branch}")
        
        if not success or not output:
            return ["No commits found"]
        
        return output.split('\n')
    
    def get_diff(self) -> str:
        """
        Get the differences between the current branch and the main branch.
        
        Returns:
            str: Difference content or error message
        """
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return "Unable to determine branches"
        
        success, output = self._run_command(f"git diff {main_branch}..{current_branch}")
        return output if success and output else "No differences found"
    
    def squash_commits(self, message: str) -> Tuple[bool, str]:
        """
        Squash all commits from the current branch into one and merge into the main branch.
        
        Args:
            message (str): The squash commit message
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return False, "Unable to determine branches"

        temp_branch = f"temp-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        success, _ = self._run_command(f"git checkout {main_branch}")
        if not success:
            return False, f"Failed to checkout {main_branch}"
        
        success, _ = self._run_command(f"git checkout -b {temp_branch}")
        if not success:
            return False, f"Failed to create temporary branch"

        success, output = self._run_command(f'git merge --squash {current_branch}')
        if not success:
            self._run_command(f"git checkout {current_branch}")
            self._run_command(f"git branch -D {temp_branch}")
            return False, f"Failed to squash merge: {output}"

        success, output = self._run_command(f'git commit -m "{message}"')
        if not success:
            self._run_command(f"git checkout {current_branch}")
            self._run_command(f"git branch -D {temp_branch}")
            return False, f"Failed to commit squashed changes: {output}"

        success, commit_hash = self._run_command(f"git rev-parse HEAD")
        if not success:
            commit_hash = "unknown"

        success, _ = self._run_command(f"git checkout {main_branch}")
        if not success:
            return False, f"Failed to checkout {main_branch}"
        
        success, _ = self._run_command(f"git merge {temp_branch}")
        if not success:
            return False, f"Failed to merge temporary branch"

        # Cleanup temporary branch
        self._run_command(f"git branch -D {temp_branch}")

        # Stay on main branch instead of returning to task branch
        return True, f"[{main_branch} {commit_hash[:7]}] {message}"
    
    def abort_changes(self) -> Tuple[bool, str]:
        """
        Abandon all changes on the current branch.
        
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        current_branch = self.get_current_branch()
        
        if not current_branch or self.config.task_prefix not in current_branch:
            return False, "Not on a task branch"

        # Reset all changes
        success, output = self._run_command("git reset --hard HEAD")
        if not success:
            return False, f"Failed to reset changes: {output}"

        # Clean untracked files
        success, output = self._run_command("git clean -fd")
        if not success:
            return False, f"Failed to clean untracked files: {output}"
        
        return True, "All changes have been abandoned"
    
    def delete_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Delete the specified branch.
        
        Args:
            branch_name (str): The name of the branch to delete
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        success, output = self._run_command(f"git branch -D {branch_name}")
        return success, output
