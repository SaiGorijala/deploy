"""
Deployment handler for SSH-based remote container deployment.
Manages SSH connections, Docker operations on remote servers, and health checks.
"""

import logging
import tempfile
import os
import httpx
import asyncio
from pathlib import Path
from typing import Tuple, Optional, Dict
from datetime import datetime
import time

try:
    import paramiko
except ImportError:
    paramiko = None

from models import TargetServerCredentials, DeploymentRequest, DeploymentMetrics
from config import Settings

logger = logging.getLogger(__name__)


class DeployHandler:
    """Handles remote deployment via SSH."""
    
    def __init__(
        self,
        settings: Settings,
        credentials: TargetServerCredentials
    ):
        """
        Initialize deployment handler.
        
        Args:
            settings: Application settings
            credentials: Target server credentials
        """
        self.settings = settings
        self.credentials = credentials
        
        if paramiko is None:
            raise ImportError("paramiko is required for SSH deployment. Install with: pip install paramiko")
        
        logger.info(f"DeployHandler initialized for {credentials.target_server_ip}")
    
    async def deploy(
        self,
        image_uri: str,
        request: DeploymentRequest
    ) -> Tuple[str, str, int]:
        """
        Deploy container to remote server.
        
        Args:
            image_uri: Full Docker image URI
            request: Deployment request with configuration
            
        Returns:
            Tuple of (container_id, server_ip, port)
            
        Raises:
            Exception: If deployment fails
        """
        logger.info(f"Starting deployment to {self.credentials.target_server_ip}")
        
        # Write PEM key to temporary secure file
        temp_pem_file = None
        try:
            temp_pem_file = self._write_temporary_pem_key()
            
            # Connect via SSH
            ssh_client = self._establish_ssh_connection(temp_pem_file)
            
            try:
                # Login to Docker on remote server
                self._remote_docker_login(ssh_client, request.docker)
                
                # Pull image
                self._remote_docker_pull(ssh_client, image_uri)
                
                # Start container
                container_id = self._remote_docker_run(
                    ssh_client,
                    image_uri,
                    request.container_port,
                    request.environment_variables or {}
                )
                
                logger.info(f"Container started: {container_id}")
                
                return (
                    container_id,
                    self.credentials.target_server_ip,
                    request.container_port
                )
                
            finally:
                ssh_client.close()
                
        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            raise
        finally:
            # Clean up temporary PEM file
            if temp_pem_file and os.path.exists(temp_pem_file):
                try:
                    os.remove(temp_pem_file)
                    logger.info("Cleaned up temporary SSH key")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temporary SSH key: {str(e)}")
    
    def _write_temporary_pem_key(self) -> str:
        """
        Write PEM key to temporary secure file.
        
        Returns:
            str: Path to temporary PEM file
        """
        # Use secure temporary file
        fd, temp_path = tempfile.mkstemp(suffix=".pem", text=True)
        
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(self.credentials.target_server_pem_file_content)
            
            # Set strict permissions (600)
            os.chmod(temp_path, self.settings.temp_ssh_key_permissions)
            
            logger.info(f"Temporary PEM key written to {temp_path}")
            return temp_path
            
        except Exception as e:
            logger.error(f"Failed to write temporary PEM key: {str(e)}")
            raise
    
    def _establish_ssh_connection(self, pem_file_path: str) -> paramiko.SSHClient:
        """
        Establish SSH connection to remote server.
        
        Args:
            pem_file_path: Path to PEM private key file
            
        Returns:
            paramiko.SSHClient: Connected SSH client
            
        Raises:
            Exception: If connection fails
        """
        logger.info(f"Establishing SSH connection to {self.credentials.target_server_ip}")
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            ssh_client.connect(
                hostname=self.credentials.target_server_ip,
                port=self.credentials.target_server_port,
                username=self.credentials.target_server_username,
                key_filename=pem_file_path,
                timeout=30
            )
            
            logger.info("SSH connection established")
            return ssh_client
            
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed: {str(e)}")
            raise Exception(f"SSH authentication failed: {str(e)}")
        except paramiko.SSHException as e:
            logger.error(f"SSH connection failed: {str(e)}")
            raise Exception(f"SSH connection failed: {str(e)}")
    
    def _remote_docker_login(
        self,
        ssh_client: paramiko.SSHClient,
        docker_creds
    ):
        """
        Execute docker login on remote server.
        
        Args:
            ssh_client: Connected SSH client
            docker_creds: Docker credentials
            
        Raises:
            Exception: If login fails
        """
        logger.info("Executing docker login on remote server")
        
        cmd = (
            f"echo '{docker_creds.docker_hub_token}' | "
            f"docker login -u {docker_creds.docker_hub_username} "
            f"--password-stdin {docker_creds.docker_registry_url}"
        )
        
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            error_output = stderr.read().decode()
            raise Exception(f"Remote docker login failed: {error_output}")
        
        logger.info("Remote docker login successful")
    
    def _remote_docker_pull(self, ssh_client: paramiko.SSHClient, image_uri: str):
        """
        Pull Docker image on remote server.
        
        Args:
            ssh_client: Connected SSH client
            image_uri: Full Docker image URI
            
        Raises:
            Exception: If pull fails
        """
        logger.info(f"Pulling image on remote server: {image_uri}")
        
        cmd = f"docker pull {image_uri}"
        
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            error_output = stderr.read().decode()
            raise Exception(f"Remote docker pull failed: {error_output}")
        
        logger.info("Image pulled successfully")
    
    def _remote_docker_run(
        self,
        ssh_client: paramiko.SSHClient,
        image_uri: str,
        port: int,
        env_vars: Dict[str, str]
    ) -> str:
        """
        Start Docker container on remote server.
        
        Args:
            ssh_client: Connected SSH client
            image_uri: Full Docker image URI
            port: Container port to expose
            env_vars: Environment variables for container
            
        Returns:
            str: Container ID
            
        Raises:
            Exception: If docker run fails
        """
        logger.info(f"Starting container on remote server")
        
        # Build environment variables
        env_string = " ".join(f"-e {k}={v}" for k, v in env_vars.items())
        
        cmd = (
            f"docker run -d -p 127.0.0.1:{port}:{port} "
            f"{env_string} {image_uri}"
        )
        
        stdin, stdout, stderr = ssh_client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code != 0:
            error_output = stderr.read().decode()
            raise Exception(f"Remote docker run failed: {error_output}")
        
        container_id = stdout.read().decode().strip()
        logger.info(f"Container started: {container_id}")
        
        return container_id
    
    async def health_check(
        self,
        server_ip: str,
        port: int,
        request: DeploymentRequest,
        max_retries: Optional[int] = None
    ) -> bool:
        """
        Perform health check on deployed container.
        
        Args:
            server_ip: Server IP address
            port: Container port
            request: Deployment request with health check config
            max_retries: Maximum retry attempts
            
        Returns:
            bool: True if container is healthy
            
        Raises:
            Exception: If health check fails after all retries
        """
        max_retries = max_retries or self.settings.health_check_max_retries
        retry_interval = self.settings.health_check_retry_interval
        timeout = self.settings.health_check_timeout_seconds
        
        health_url = (
            f"http://{server_ip}:{port}{request.container_health_check_path}"
        )
        
        logger.info(f"Starting health check: {health_url}")
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(health_url)
                    
                    if response.status_code == 200:
                        logger.info("Health check passed")
                        return True
                    else:
                        logger.warning(
                            f"Health check returned status {response.status_code}"
                        )
                        
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(
                    f"Health check attempt {attempt + 1}/{max_retries} failed: {str(e)}"
                )
            
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_interval)
        
        raise Exception(
            f"Health check failed after {max_retries} attempts. "
            f"Container may not be ready or health endpoint not accessible."
        )
