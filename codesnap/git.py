import os
import subprocess
import re
from datetime import datetime
from typing import Tuple, List, Optional, Union
from colorama import Fore
from .config import ConfigOptions

class GitOps:
    def __init__(self) -> None:
        self.config = ConfigOptions()
    
    def _run_command(self, command: str, capture_output: bool = True) -> Tuple[bool, Optional[str]]:
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
        return self._run_command("git rev-parse --is-inside-work-tree")[0]
    
    def initialize_repository(self, branch_name: str = "master") -> bool:
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
        success, output = self._run_command("git branch --show-current")
        return output if success else None
    
    def create_branch(self, branch_name: str) -> Tuple[bool, str]:
        success, output = self._run_command(f"git checkout -b {branch_name}")
        return success, output
    
    def checkout_branch(self, branch_name: str) -> Tuple[bool, str]:
        success, output = self._run_command(f"git checkout {branch_name}")
        return success, output
    
    def get_changes(self) -> str:
        success, output = self._run_command("git status --porcelain")
        return output if success else ""
    
    def commit_changes(self, message: str) -> Tuple[bool, str]:
        # Check if there are any changes to commit
        if not self.get_changes():
            return False, "No changes to commit"
        
        # Get current branch to include in commit message
        current_branch = self.get_current_branch()
        if self.config.task_prefix in current_branch:
            # Add all changes
            success, _ = self._run_command("git add .")
            if not success:
                return False, "Failed to stage changes"
            
            # Commit with branch name
            success, output = self._run_command(f'git commit -m "{message}"')
            if not success:
                return False, f"Failed to commit: {output}"
            
            # Parse commit hash and return formatted output
            commit_hash_match = re.search(r'\[.*\s([a-f0-9]+)\]', output)
            commit_hash = commit_hash_match.group(1) if commit_hash_match else "unknown"
            
            return True, f"[{current_branch} {commit_hash}] {message}"
        else:
            return False, "Not on a task branch"
    
    def get_main_branch(self) -> Optional[str]:
        # Try to determine main branch (master, main, etc.)
        for branch in ["master", "main"]:
            success, _ = self._run_command(f"git rev-parse --verify {branch}")
            if success:
                return branch
        return None
    
    def get_task_log(self, show_graph: bool = False) -> List[str]:
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return ["Unable to determine branches"]
        
        # Get commits between main branch and current task branch
        graph_option = "--graph --oneline --decorate" if show_graph else "--oneline"
        success, output = self._run_command(f"git log {graph_option} {main_branch}..{current_branch}")
        
        if not success or not output:
            return ["No commits found"]
        
        return output.split('\n')
    
    def get_diff(self) -> str:
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return "Unable to determine branches"
        
        success, output = self._run_command(f"git diff {main_branch}..{current_branch}")
        return output if success and output else "No differences found"
    
    def squash_commits(self, message: str) -> Tuple[bool, str]:
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return False, "Unable to determine branches"
        
        # Create a temporary branch at the same point as main
        temp_branch = f"temp-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        success, _ = self._run_command(f"git checkout {main_branch}")
        if not success:
            return False, f"Failed to checkout {main_branch}"
        
        success, _ = self._run_command(f"git checkout -b {temp_branch}")
        if not success:
            return False, f"Failed to create temporary branch"
        
        # Merge the task branch with squash
        success, output = self._run_command(f'git merge --squash {current_branch}')
        if not success:
            # Cleanup and return error
            self._run_command(f"git checkout {current_branch}")
            self._run_command(f"git branch -D {temp_branch}")
            return False, f"Failed to squash merge: {output}"
        
        # Commit the squashed changes
        success, output = self._run_command(f'git commit -m "{message}"')
        if not success:
            # Cleanup and return error
            self._run_command(f"git checkout {current_branch}")
            self._run_command(f"git branch -D {temp_branch}")
            return False, f"Failed to commit squashed changes: {output}"
        
        # Get the commit hash
        success, commit_hash = self._run_command(f"git rev-parse HEAD")
        if not success:
            commit_hash = "unknown"
        
        # Checkout main branch and merge temp branch
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
        success, output = self._run_command(f"git branch -D {branch_name}")
        return success, output
