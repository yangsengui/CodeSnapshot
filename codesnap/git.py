import os
from datetime import datetime
from typing import Tuple, List, Optional
import git
from git import Repo, GitCommandError

from .config import ConfigOptions


class GitOps:
    def __init__(self) -> None:
        self.config = ConfigOptions()
        self._repo = None
    
    @property
    def repo(self):
        """
        Get the git.Repo instance for the current directory.
        
        Returns:
            git.Repo: Repository instance
        """
        if self._repo is None and self.is_git_repo():
            try:
                self._repo = Repo(os.getcwd())
            except GitCommandError:
                pass
        return self._repo
    
    def is_git_repo(self) -> bool:
        """
        Check if the current directory is a Git repository.
        
        Returns:
            bool: True if it's a Git repository, False otherwise
        """
        try:
            Repo(os.getcwd())
            return True
        except (git.exc.InvalidGitRepositoryError, git.exc.NoSuchPathError):
            return False
    
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
        
        try:
            # Initialize repository
            repo = Repo.init(os.getcwd())
            self._repo = repo
            
            # Create a .gitignore file if it doesn't exist
            if not os.path.exists(".gitignore"):
                with open(".gitignore", "w") as f:
                    f.write("# CodeSnap auto-generated .gitignore\n")
            
            # Add all files and create initial commit
            repo.git.add(A=True)
            repo.git.checkout(b=branch_name)
            repo.git.commit(m="Initial commit")
            return True
        except GitCommandError:
            return False
    
    def get_current_branch(self) -> Optional[str]:
        """
        Get the name of the current Git branch.
        
        Returns:
            Optional[str]: Current branch name, or None if an error occurs
        """
        if not self.repo:
            return None
        try:
            return self.repo.active_branch.name
        except (GitCommandError, TypeError):
            return None
    
    def create_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Create and switch to a new branch.
        
        Args:
            branch_name (str): The name of the new branch
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
        
        try:
            self.repo.git.checkout(b=branch_name)
            return True, f"Switched to a new branch '{branch_name}'"
        except GitCommandError as e:
            return False, str(e)
    
    def checkout_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Switch to the specified branch.
        
        Args:
            branch_name (str): The name of the branch to switch to
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
        
        try:
            self.repo.git.checkout(branch_name)
            return True, f"Switched to branch '{branch_name}'"
        except GitCommandError as e:
            return False, str(e)
    
    def get_changes(self) -> str:
        """
        Get the change status of the current working directory.
        
        Returns:
            str: A brief description of the working directory status
        """
        if not self.repo:
            return ""
        
        try:
            return self.repo.git.status(porcelain=True)
        except GitCommandError:
            return ""
    
    def commit_changes(self, message: str) -> Tuple[bool, str]:
        """
        Commit current changes.
        
        Args:
            message (str): The commit message
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
            
        if not self.get_changes():
            return False, "No changes to commit"

        current_branch = self.get_current_branch()
        if self.config.task_prefix in current_branch:
            try:
                self.repo.git.add(A=True)
                self.repo.git.commit(m=message)
                commit_hash = self.repo.head.commit.hexsha[:7]
                return True, f"[{current_branch} {commit_hash}] {message}"
            except GitCommandError as e:
                return False, f"Failed to commit: {str(e)}"
        else:
            return False, "Not on a task branch"
    
    def get_main_branch(self) -> Optional[str]:
        """
        Get the main branch name (master or main).
        
        Returns:
            Optional[str]: The main branch name, or None if not found
        """
        if not self.repo:
            return None
            
        for branch in ["master", "main"]:
            try:
                if branch in [ref.name for ref in self.repo.refs]:
                    return branch
            except GitCommandError:
                pass
        return None
    
    def get_task_log(self, show_graph: bool = False) -> List[str]:
        """
        Get the commit log of the task branch relative to the main branch.
        
        Args:
            show_graph (bool): Whether to display a commit graph, defaults to False
            
        Returns:
            List[str]: List of commit log lines
        """
        if not self.repo:
            return ["Not a git repository"]
            
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return ["Unable to determine branches"]

        try:
            if show_graph:
                output = self.repo.git.log("--graph", "--oneline", "--decorate", f"{main_branch}..{current_branch}")
            else:
                output = self.repo.git.log("--oneline", f"{main_branch}..{current_branch}")
                
            if not output:
                return ["No commits found"]
                
            return output.split('\n')
        except GitCommandError:
            return ["No commits found"]
    
    def get_diff(self) -> str:
        """
        Get the differences between the current branch and the main branch.
        
        Returns:
            str: Difference content or error message
        """
        if not self.repo:
            return "Not a git repository"
            
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return "Unable to determine branches"
        
        try:
            output = self.repo.git.diff(f"{main_branch}..{current_branch}")
            return output if output else "No differences found"
        except GitCommandError as e:
            return str(e)
    
    def verify_branch_exists(self, branch_name: str) -> bool:
        """
        Check if a branch exists in the repository.
        
        Args:
            branch_name (str): The name of the branch to check
            
        Returns:
            bool: True if the branch exists, False otherwise
        """
        if not self.repo:
            return False
        
        try:
            # Check if the branch exists in the list of branches
            return branch_name in [head.name for head in self.repo.heads]
        except GitCommandError:
            return False
    
    def merge_without_commit(self, branch_name: str) -> Tuple[bool, str]:
        """
        Merge a branch into the current branch without committing.
        
        Args:
            branch_name (str): The name of the branch to merge
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
        
        try:
            self.repo.git.merge("--no-commit", "--no-ff", branch_name)
            return True, f"Started merge of '{branch_name}'"
        except GitCommandError as e:
            return False, str(e)
    
    def abort_merge(self) -> Tuple[bool, str]:
        """
        Abort the current merge operation.
        
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
        
        try:
            self.repo.git.merge("--abort")
            return True, "Merge aborted"
        except GitCommandError as e:
            return False, str(e)
    
    def merge_with_commit(self, branch_name: str, message: str) -> Tuple[bool, str]:
        """
        Merge a branch into the current branch with a commit.
        
        Args:
            branch_name (str): The name of the branch to merge
            message (str): The commit message
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
        
        try:
            self.repo.git.merge("--no-ff", branch_name, "-m", message)
            commit_hash = self.repo.head.commit.hexsha[:7]
            return True, f"[{self.get_current_branch()} {commit_hash}] {message}"
        except GitCommandError as e:
            return False, str(e)
    
    def squash_commits(self, message: str) -> Tuple[bool, str]:
        """
        Squash all commits from the current branch into one and merge into the main branch.
        
        Args:
            message (str): The squash commit message
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
            
        main_branch = self.get_main_branch()
        current_branch = self.get_current_branch()
        
        if not main_branch or not current_branch:
            return False, "Unable to determine branches"

        temp_branch = f"temp-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        try:
            # Checkout main branch
            self.repo.git.checkout(main_branch)
            
            # Create temporary branch
            self.repo.git.checkout(b=temp_branch)
            
            # Squash merge the current branch
            self.repo.git.merge("--squash", current_branch)
            
            # Commit the squashed changes
            self.repo.git.commit(m=message)
            
            # Get commit hash
            commit_hash = self.repo.head.commit.hexsha[:7]
            
            # Checkout main branch again
            self.repo.git.checkout(main_branch)
            
            # Merge the temporary branch
            self.repo.git.merge(temp_branch)
            
            # Delete temporary branch
            self.repo.git.branch(D=temp_branch)
            
            return True, f"[{main_branch} {commit_hash}] {message}"
        except GitCommandError as e:
            # Try to cleanup
            try:
                self.repo.git.checkout(current_branch)
                if temp_branch in [ref.name for ref in self.repo.refs]:
                    self.repo.git.branch(D=temp_branch)
            except GitCommandError:
                pass
            return False, str(e)
    
    def abort_changes(self) -> Tuple[bool, str]:
        """
        Abandon all changes on the current branch.
        
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
            
        current_branch = self.get_current_branch()
        
        if not current_branch or self.config.task_prefix not in current_branch:
            return False, "Not on a task branch"

        try:
            # Reset all changes
            self.repo.git.reset("--hard", "HEAD")
            
            # Clean untracked files
            self.repo.git.clean("-fd")
            
            return True, "All changes have been abandoned"
        except GitCommandError as e:
            return False, str(e)
    
    def delete_branch(self, branch_name: str) -> Tuple[bool, str]:
        """
        Delete the specified branch.
        
        Args:
            branch_name (str): The name of the branch to delete
            
        Returns:
            Tuple[bool, str]: (success flag, output or error message)
        """
        if not self.repo:
            return False, "Not a git repository"
            
        try:
            self.repo.git.branch(D=branch_name)
            return True, f"Deleted branch {branch_name}"
        except GitCommandError as e:
            return False, str(e)
