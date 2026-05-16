"""
Git handler for authenticated repository cloning.
Safely manages Git credentials and isolation of cloned repositories.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional
import urllib.parse

from models import GitCredentials
from config import Settings

logger = logging.getLogger(__name__)


class GitHandler:
    """Handles Git repository operations with authentication."""
    
    def __init__(
        self,
        settings: Settings,
        workspace_root: Path,
        credentials: GitCredentials
    ):
        """
        Initialize Git handler.
        
        Args:
            settings: Application settings
            workspace_root: Root workspace directory
            credentials: Git authentication credentials
        """
        self.settings = settings
        self.workspace_root = workspace_root
        self.credentials = credentials
        self.repo_path = workspace_root / "repository"
        
        logger.info(f"GitHandler initialized for {credentials.git_repo_url}")
    
    async def clone_repository(self) -> Path:
        """
        Clone repository with authentication.
        
        Returns:
            Path: Path to cloned repository
            
        Raises:
            subprocess.CalledProcessError: If clone fails
        """
        logger.info(f"Cloning repository: {self.credentials.git_repo_url}")
        
        # Prepare authenticated URL
        auth_url = self._prepare_auth_url(
            self.credentials.git_repo_url,
            self.credentials.git_username,
            self.credentials.git_token
        )
        
        try:
            # Clone repository
            subprocess.run(
                ["git", "clone", auth_url, str(self.repo_path)],
                check=True,
                capture_output=True,
                timeout=300
            )
            
            # Configure git for safe operation
            subprocess.run(
                ["git", "config", "user.email", "devops-pipeline@local"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            subprocess.run(
                ["git", "config", "user.name", "DevOps Pipeline"],
                cwd=self.repo_path,
                check=True,
                capture_output=True
            )
            
            logger.info(f"Repository cloned successfully to {self.repo_path}")
            return self.repo_path
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Git clone failed: {error_msg}")
            raise Exception(f"Git clone failed: {error_msg}")
        except subprocess.TimeoutExpired:
            logger.error("Git clone timed out")
            raise Exception("Git clone operation timed out")
        except Exception as e:
            logger.error(f"Unexpected error during git clone: {str(e)}")
            raise
    
    def get_commit_hash(self) -> str:
        """
        Get current commit hash from cloned repository.
        
        Returns:
            str: Current commit hash
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get commit hash: {str(e)}")
            raise
    
    def get_repository_info(self) -> dict:
        """
        Get repository information (branch, commit, origin).
        
        Returns:
            dict: Repository metadata
        """
        try:
            # Get current branch
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            branch = branch_result.stdout.strip()
            
            # Get commit hash
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            commit = commit_result.stdout.strip()
            
            # Get remote URL
            remote_result = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
                text=True
            )
            remote = remote_result.stdout.strip()
            
            return {
                "branch": branch,
                "commit": commit,
                "remote": remote,
                "local_path": str(self.repo_path)
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get repository info: {str(e)}")
            return {
                "branch": "unknown",
                "commit": "unknown",
                "remote": "unknown",
                "local_path": str(self.repo_path)
            }
    
    @staticmethod
    def _prepare_auth_url(
        repo_url: str,
        username: str,
        token: str
    ) -> str:
        """
        Prepare authenticated Git URL with token.
        
        Args:
            repo_url: Original repository URL
            username: Git username
            token: Personal access token
            
        Returns:
            str: Authenticated URL
        """
        # Handle HTTPS URLs
        if repo_url.startswith("https://"):
            # Extract components
            parts = repo_url.replace("https://", "").split("/", 1)
            host = parts[0]
            path = parts[1] if len(parts) > 1 else ""
            
            # Encode credentials
            encoded_user = urllib.parse.quote(username, safe="")
            encoded_token = urllib.parse.quote(token, safe="")
            
            return f"https://{encoded_user}:{encoded_token}@{host}/{path}"
        
        # Handle SSH URLs (leave as-is, assumes SSH key configured)
        elif repo_url.startswith("git@"):
            return repo_url
        
        else:
            raise ValueError(f"Unsupported Git URL format: {repo_url}")
    
    def cleanup(self):
        """Clean up repository files."""
        try:
            if self.repo_path.exists():
                import shutil
                shutil.rmtree(self.repo_path)
                logger.info(f"Cleaned up repository at {self.repo_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup repository: {str(e)}")
