"""
SonarQube handler for code quality analysis.
Manages SonarQube project setup, analysis execution, and metrics polling.
"""

import subprocess
import logging
import httpx
import asyncio
import json
from pathlib import Path
from typing import Optional
import time

from models import SonarQubeConfig, DeploymentRequest, SonarQubeMetrics
from config import Settings

logger = logging.getLogger(__name__)


class SonarQubeHandler:
    """Handles SonarQube code quality analysis."""
    
    def __init__(
        self,
        settings: Settings,
        config: SonarQubeConfig
    ):
        """
        Initialize SonarQube handler.
        
        Args:
            settings: Application settings
            config: SonarQube configuration
        """
        self.settings = settings
        self.config = config
        self.sonar_host = config.sonar_host_url.rstrip("/")
        self.sonar_token = config.sonar_token
        
        logger.info(f"SonarQubeHandler initialized for {self.sonar_host}")
    
    async def analyze(
        self,
        repo_path: Path,
        request: DeploymentRequest
    ) -> Optional[SonarQubeMetrics]:
        """
        Execute SonarQube analysis and return metrics.
        
        Args:
            repo_path: Path to repository to analyze
            request: Deployment request with config
            
        Returns:
            SonarQubeMetrics with analysis results, or None if analysis fails
        """
        logger.info(f"Starting SonarQube analysis for {repo_path}")
        
        # Generate or use provided project key
        project_key = self.config.sonar_project_key or self._generate_project_key(request)
        
        try:
            # Generate sonar-project.properties
            self._generate_sonar_properties(repo_path, project_key)
            
            # Execute sonar-scanner
            self._execute_scanner(repo_path)
            
            # Poll for analysis completion and fetch metrics
            metrics = await self._poll_for_metrics(project_key)
            
            logger.info(f"SonarQube analysis completed for {project_key}")
            return metrics
            
        except Exception as e:
            logger.error(f"SonarQube analysis failed: {str(e)}")
            raise
    
    def _generate_sonar_properties(self, repo_path: Path, project_key: str):
        """
        Generate sonar-project.properties file.
        
        Args:
            repo_path: Repository path
            project_key: SonarQube project key
        """
        properties_content = f"""
sonar.projectKey={project_key}
sonar.projectName={project_key}
sonar.projectVersion=1.0
sonar.sources=.
sonar.exclusions=**/node_modules/**,**/venv/**,**/build/**,**/.git/**,**/test/**
sonar.language.java.binaries=target/classes
sonar.host.url={self.sonar_host}
sonar.login={self.sonar_token}
"""
        
        properties_file = repo_path / "sonar-project.properties"
        with open(properties_file, 'w') as f:
            f.write(properties_content.strip())
        
        logger.info(f"Generated sonar-project.properties at {properties_file}")
    
    def _execute_scanner(self, repo_path: Path):
        """
        Execute sonar-scanner command.
        
        Args:
            repo_path: Repository path
            
        Raises:
            subprocess.CalledProcessError: If scanner fails
        """
        logger.info("Executing sonar-scanner")
        
        try:
            result = subprocess.run(
                ["sonar-scanner"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            if result.returncode != 0:
                raise Exception(f"sonar-scanner failed: {result.stderr}")
            
            logger.info("sonar-scanner completed successfully")
            
        except FileNotFoundError:
            raise Exception(
                "sonar-scanner not found. Please install SonarQube Scanner: "
                "https://docs.sonarsource.com/sonarqube/latest/analyzing-source-code/scanners/sonarscanner/"
            )
    
    async def _poll_for_metrics(self, project_key: str) -> SonarQubeMetrics:
        """
        Poll SonarQube API for analysis completion and metrics.
        
        Args:
            project_key: SonarQube project key
            
        Returns:
            SonarQubeMetrics with analysis results
            
        Raises:
            Exception: If polling times out or API returns error
        """
        logger.info(f"Polling for metrics for project {project_key}")
        
        max_attempts = self.settings.sonarqube_max_polling_attempts
        poll_interval = self.settings.sonarqube_polling_interval
        
        async with httpx.AsyncClient(
            auth=(self.sonar_token, ""),
            timeout=self.settings.request_timeout_seconds
        ) as client:
            for attempt in range(max_attempts):
                try:
                    # Get ce task (background task)
                    ce_response = await client.get(
                        f"{self.sonar_host}/api/ce/activity",
                        params={"type": "REPORT", "status": "IN_PROGRESS,PENDING"}
                    )
                    ce_response.raise_for_status()
                    
                    # Check if analysis is done
                    tasks = ce_response.json().get("tasks", [])
                    if not tasks:
                        # Analysis complete, get metrics
                        return await self._fetch_metrics(client, project_key)
                    
                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                    
                except Exception as e:
                    logger.warning(f"Polling attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(poll_interval)
        
        raise Exception(
            f"SonarQube analysis polling timed out after {max_attempts * poll_interval} seconds"
        )
    
    async def _fetch_metrics(
        self,
        client: httpx.AsyncClient,
        project_key: str
    ) -> SonarQubeMetrics:
        """
        Fetch metrics from SonarQube API.
        
        Args:
            client: HTTP client with authentication
            project_key: SonarQube project key
            
        Returns:
            SonarQubeMetrics
        """
        # Get project details
        project_response = await client.get(
            f"{self.sonar_host}/api/projects/show",
            params={"project": project_key}
        )
        project_response.raise_for_status()
        project_data = project_response.json()
        
        # Get quality gate
        qg_response = await client.get(
            f"{self.sonar_host}/api/qualitygates/project_status",
            params={"projectKey": project_key}
        )
        qg_response.raise_for_status()
        qg_data = qg_response.json()
        
        # Get detailed metrics
        metrics_response = await client.get(
            f"{self.sonar_host}/api/measures/component",
            params={
                "component": project_key,
                "metricKeys": "bugs,vulnerabilities,code_smells,coverage"
            }
        )
        metrics_response.raise_for_status()
        metrics_data = metrics_response.json()
        
        # Parse metrics
        measures = {m["metric"]: m.get("value", "0") for m in metrics_data.get("component", {}).get("measures", [])}
        
        qg_status = qg_data.get("projectStatus", {}).get("status", "UNKNOWN")
        
        return SonarQubeMetrics(
            project_key=project_key,
            quality_gate_status=qg_status,
            bugs=int(measures.get("bugs", 0)),
            vulnerabilities=int(measures.get("vulnerabilities", 0)),
            code_smells=int(measures.get("code_smells", 0)),
            coverage=float(measures.get("coverage", 0)) if measures.get("coverage") else None,
            dashboard_url=f"{self.sonar_host}/dashboard?id={project_key}"
        )
    
    @staticmethod
    def _generate_project_key(request: DeploymentRequest) -> str:
        """
        Generate SonarQube project key from deployment request.
        
        Args:
            request: Deployment request
            
        Returns:
            str: Generated project key
        """
        # Extract repo name from URL
        repo_url = request.git.git_repo_url.rstrip("/").rstrip(".git")
        repo_name = repo_url.split("/")[-1]
        
        # Sanitize for SonarQube (alphanumeric, dash, underscore)
        import re
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", repo_name)
        
        return f"devops_{sanitized}"
