"""
Pydantic models for request/response validation and internal data structures.
Ensures type safety and provides comprehensive schema documentation.
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class GitCredentials(BaseModel):
    """Git repository authentication credentials."""
    git_repo_url: str = Field(..., description="Git repository URL")
    git_username: str = Field(..., description="Git username")
    git_token: str = Field(..., description="Git personal access token")
    
    @validator('git_repo_url')
    def validate_git_url(cls, v):
        if not v.endswith('.git'):
            v = v + '.git'
        return v


class TargetServerCredentials(BaseModel):
    """SSH target server authentication."""
    target_server_ip: str = Field(..., description="Target server IP address")
    target_server_username: str = Field(default="ubuntu", description="SSH username")
    target_server_pem_file_content: str = Field(..., description="Raw SSH private key content")
    target_server_port: int = Field(default=22, description="SSH port")
    
    @validator('target_server_port')
    def validate_port(cls, v):
        if not 1 <= v <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class DockerHubCredentials(BaseModel):
    """Docker Hub authentication and configuration."""
    docker_hub_username: str = Field(..., description="Docker Hub username")
    docker_hub_token: str = Field(..., description="Docker Hub personal access token")
    docker_image_name: Optional[str] = Field(default=None, description="Docker image name (auto-generated if omitted)")
    docker_registry_url: str = Field(default="docker.io", description="Docker registry URL")


class SonarQubeConfig(BaseModel):
    """SonarQube analysis configuration."""
    sonar_host_url: str = Field(..., description="SonarQube instance URL")
    sonar_token: str = Field(..., description="SonarQube authentication token")
    sonar_project_key: Optional[str] = Field(default=None, description="SonarQube project key (auto-generated if omitted)")


class TrivyConfig(BaseModel):
    """Trivy vulnerability scanner configuration."""
    trivy_username: Optional[str] = Field(default=None, description="Trivy registry username")
    trivy_token: Optional[str] = Field(default=None, description="Trivy registry token")
    trivy_severity_threshold: str = Field(default="HIGH", description="Minimum severity to fail on")


class AIAgentConfig(BaseModel):
    """AI self-healing agent configuration."""
    max_retries: int = Field(default=3, description="Maximum retry attempts per stage")
    timeout_seconds: int = Field(default=300, description="Timeout for API requests")


class DeploymentRequest(BaseModel):
    """Complete deployment request with all credentials and configuration."""
    git: GitCredentials
    target_server: TargetServerCredentials
    docker: DockerHubCredentials
    sonarqube: SonarQubeConfig
    trivy: TrivyConfig = Field(default_factory=TrivyConfig)
    ai_agent: AIAgentConfig = Field(default_factory=AIAgentConfig)
    
    # Optional deployment configuration
    deployment_name: Optional[str] = Field(default=None, description="Human-readable deployment name")
    container_port: int = Field(default=8080, description="Port exposed by container")
    container_health_check_path: str = Field(default="/health", description="Health check endpoint")
    environment_variables: Optional[Dict[str, str]] = Field(default=None, description="Container environment variables")


class PipelineStatus(str, Enum):
    """Pipeline execution status enumeration."""
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PipelineStage(str, Enum):
    """Pipeline execution stages."""
    GIT_CLONE = "git_clone"
    SONARQUBE = "sonarqube"
    DOCKER_BUILD = "docker_build"
    DOCKER_PUSH = "docker_push"
    TRIVY_SCAN = "trivy_scan"
    DEPLOY = "deploy"
    HEALTH_CHECK = "health_check"


class SonarQubeMetrics(BaseModel):
    """SonarQube quality metrics."""
    project_key: str
    quality_gate_status: str = Field(..., description="PASSED or FAILED")
    bugs: int = Field(default=0)
    vulnerabilities: int = Field(default=0)
    code_smells: int = Field(default=0)
    coverage: Optional[float] = Field(default=None, description="Code coverage percentage")
    dashboard_url: str


class VulnerabilitySummary(BaseModel):
    """Vulnerability scan summary by severity."""
    critical: int = Field(default=0)
    high: int = Field(default=0)
    medium: int = Field(default=0)
    low: int = Field(default=0)
    timestamp: str
    report_url: Optional[str] = Field(default=None)


class DeploymentMetrics(BaseModel):
    """Final deployment metrics and connection details."""
    docker_hub_image_uri: str
    target_server_ip: str
    application_port: int
    container_id: Optional[str] = Field(default=None)
    validation_url: str
    deployment_time_seconds: float


class AIFix(BaseModel):
    """Record of an AI-powered fix application."""
    stage: str
    error_message: str
    ai_fix_applied: str
    retry_attempt: int
    fix_timestamp: str


class DeploymentResponse(BaseModel):
    """Response for deployment initiation."""
    deployment_id: str
    status: str
    message: str
    initiated_at: str


class PipelineResult(BaseModel):
    """Complete pipeline execution result."""
    deployment_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    
    sonarqube: Optional[SonarQubeMetrics] = None
    trivy: Optional[VulnerabilitySummary] = None
    deployment: Optional[DeploymentMetrics] = None
    ai_fixes: List[AIFix] = Field(default_factory=list)
    
    logs: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class LogEntry(BaseModel):
    """Individual log entry with timestamp."""
    timestamp: str
    stage: str
    level: str = Field(..., description="DEBUG, INFO, WARNING, ERROR")
    message: str
    details: Optional[Dict[str, Any]] = None


class HealthCheckResult(BaseModel):
    """Result of container health check."""
    healthy: bool
    response_code: int
    response_time_ms: float
    endpoint: str
    timestamp: str
