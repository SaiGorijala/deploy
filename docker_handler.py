"""
Docker handler for building and pushing Docker images.
Manages Docker login, build, tag, and push operations.
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional
import re

from models import DockerHubCredentials, DeploymentRequest
from config import Settings

logger = logging.getLogger(__name__)


class DockerHandler:
    """Handles Docker image building and pushing."""
    
    def __init__(
        self,
        settings: Settings,
        credentials: DockerHubCredentials
    ):
        """
        Initialize Docker handler.
        
        Args:
            settings: Application settings
            credentials: Docker Hub credentials
        """
        self.settings = settings
        self.credentials = credentials
        
        logger.info(f"DockerHandler initialized for {credentials.docker_hub_username}")
    
    async def build_and_push(
        self,
        repo_path: Path,
        request: DeploymentRequest
    ) -> str:
        """
        Build Docker image and push to registry.
        
        Args:
            repo_path: Path to repository with Dockerfile
            request: Deployment request with configuration
            
        Returns:
            str: Full image URI (e.g., docker.io/user/image:tag)
            
        Raises:
            Exception: If build or push fails
        """
        logger.info(f"Building Docker image from {repo_path}")
        
        # Verify Dockerfile exists
        dockerfile_path = repo_path / "Dockerfile"
        if not dockerfile_path.exists():
            raise Exception(f"Dockerfile not found at {dockerfile_path}")
        
        # Generate image name and tag
        image_name = self._generate_image_name(request)
        image_tag = self._generate_tag()
        full_image_uri = f"{self.credentials.docker_registry_url}/{image_name}:{image_tag}"
        
        try:
            # Login to Docker registry
            self._docker_login()
            
            # Build image
            self._build_image(repo_path, full_image_uri)
            
            # Push to registry
            self._push_image(full_image_uri)
            
            logger.info(f"Docker image pushed successfully: {full_image_uri}")
            return full_image_uri
            
        except Exception as e:
            logger.error(f"Docker build/push failed: {str(e)}")
            raise
    
    def _docker_login(self):
        """
        Execute docker login with credentials.
        
        Raises:
            subprocess.CalledProcessError: If login fails
        """
        logger.info(f"Logging into Docker registry")
        
        try:
            result = subprocess.run(
                [
                    "docker",
                    "login",
                    "-u", self.credentials.docker_hub_username,
                    "-p", self.credentials.docker_hub_token,
                    self.credentials.docker_registry_url
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                raise Exception(f"Docker login failed: {result.stderr}")
            
            logger.info("Docker login successful")
            
        except FileNotFoundError:
            raise Exception("Docker CLI not found. Please install Docker.")
        except subprocess.TimeoutExpired:
            raise Exception("Docker login timed out")
    
    def _build_image(self, repo_path: Path, image_uri: str):
        """
        Build Docker image.
        
        Args:
            repo_path: Path to repository
            image_uri: Full image URI
            
        Raises:
            subprocess.CalledProcessError: If build fails
        """
        logger.info(f"Building image: {image_uri}")
        
        try:
            result = subprocess.run(
                ["docker", "build", "-t", image_uri, str(repo_path)],
                capture_output=True,
                text=True,
                timeout=1800
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Docker build failed:\n{error_msg}")
            
            logger.info("Docker build completed successfully")
            
        except subprocess.TimeoutExpired:
            raise Exception("Docker build timed out (exceeded 30 minutes)")
    
    def _push_image(self, image_uri: str):
        """
        Push Docker image to registry.
        
        Args:
            image_uri: Full image URI
            
        Raises:
            subprocess.CalledProcessError: If push fails
        """
        logger.info(f"Pushing image: {image_uri}")
        
        try:
            result = subprocess.run(
                ["docker", "push", image_uri],
                capture_output=True,
                text=True,
                timeout=1200
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                raise Exception(f"Docker push failed:\n{error_msg}")
            
            logger.info(f"Image pushed successfully: {image_uri}")
            
        except subprocess.TimeoutExpired:
            raise Exception("Docker push timed out (exceeded 20 minutes)")
    
    def _generate_image_name(self, request: DeploymentRequest) -> str:
        """
        Generate Docker image name.
        
        Args:
            request: Deployment request
            
        Returns:
            str: Image name (user/repo format)
        """
        if self.credentials.docker_image_name:
            return self.credentials.docker_image_name
        
        # Generate from repository URL
        repo_url = request.git.git_repo_url.rstrip("/").rstrip(".git")
        repo_name = repo_url.split("/")[-1]
        
        # Sanitize for Docker (lowercase, alphanumeric, dash)
        import re
        sanitized = re.sub(r"[^a-z0-9\-_]", "", repo_name.lower())
        
        return f"{self.credentials.docker_hub_username}/{sanitized}"
    
    @staticmethod
    def _generate_tag() -> str:
        """
        Generate Docker image tag.
        
        Returns:
            str: Image tag (timestamp-based)
        """
        from datetime import datetime
        return datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    def cleanup_local_image(self, image_uri: str):
        """
        Clean up local Docker image after pushing.
        
        Args:
            image_uri: Full image URI
        """
        try:
            subprocess.run(
                ["docker", "rmi", image_uri],
                capture_output=True,
                timeout=30
            )
            logger.info(f"Cleaned up local image: {image_uri}")
        except Exception as e:
            logger.warning(f"Failed to cleanup local image: {str(e)}")
