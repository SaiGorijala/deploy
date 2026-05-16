"""
Application configuration management using Pydantic settings.
Handles environment variables, defaults, and runtime configuration.
"""

from pydantic import BaseSettings, Field
from typing import Optional
import os


class Settings(BaseSettings):
    """Application-wide settings managed through environment variables."""
    
    # Application configuration
    app_name: str = Field(default="DevOps Pipeline Orchestrator", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Ollama AI configuration (SSH Reverse Tunnel)
    ollama_endpoint: str = Field(
        default="http://127.0.0.1:11434",
        env="OLLAMA_ENDPOINT",
        description="Ollama instance endpoint via SSH reverse tunnel"
    )
    ollama_model: str = Field(
        default="deepseek-coder:6.7b",
        env="OLLAMA_MODEL",
        description="Ollama model to use for AI fixes"
    )
    ollama_temperature: float = Field(
        default=0.2,
        env="OLLAMA_TEMPERATURE",
        description="Temperature for AI model responses (0.0-1.0)"
    )
    ollama_timeout_seconds: int = Field(
        default=300,
        env="OLLAMA_TIMEOUT_SECONDS",
        description="Timeout for Ollama API requests"
    )
    
    # Working directory configuration
    workspace_root: str = Field(
        default="/tmp/devops_pipeline",
        env="WORKSPACE_ROOT",
        description="Root directory for pipeline workspaces"
    )
    
    # Temporary file handling
    temp_ssh_key_permissions: int = Field(
        default=0o600,
        env="TEMP_SSH_KEY_PERMISSIONS",
        description="File permissions for temporary SSH keys"
    )
    
    # Pipeline execution configuration
    max_pipeline_retries: int = Field(
        default=3,
        env="MAX_PIPELINE_RETRIES",
        description="Maximum retry attempts per pipeline stage"
    )
    pipeline_timeout_seconds: int = Field(
        default=1800,
        env="PIPELINE_TIMEOUT_SECONDS",
        description="Timeout for entire pipeline execution"
    )
    
    # Docker configuration
    docker_socket_path: str = Field(
        default="/var/run/docker.sock",
        env="DOCKER_SOCKET_PATH",
        description="Path to Docker daemon socket"
    )
    
    # SonarQube configuration
    sonarqube_polling_interval: int = Field(
        default=5,
        env="SONARQUBE_POLLING_INTERVAL",
        description="Interval in seconds to poll SonarQube API"
    )
    sonarqube_max_polling_attempts: int = Field(
        default=120,
        env="SONARQUBE_MAX_POLLING_ATTEMPTS",
        description="Maximum polling attempts before timeout"
    )
    
    # Trivy configuration
    trivy_severity_levels: list = Field(
        default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        env="TRIVY_SEVERITY_LEVELS",
        description="Supported severity levels in order"
    )
    
    # Logging configuration
    log_level: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_file_path: Optional[str] = Field(
        default=None,
        env="LOG_FILE_PATH",
        description="Optional file path for log output"
    )
    
    # Security configuration
    enable_cleanup_on_success: bool = Field(
        default=True,
        env="ENABLE_CLEANUP_ON_SUCCESS",
        description="Clean up temporary files after successful deployment"
    )
    enable_cleanup_on_failure: bool = Field(
        default=False,
        env="ENABLE_CLEANUP_ON_FAILURE",
        description="Clean up temporary files after failed deployment for debugging"
    )
    secure_credential_handling: bool = Field(
        default=True,
        env="SECURE_CREDENTIAL_HANDLING",
        description="Clear credentials from memory after use"
    )
    
    # Network configuration
    request_timeout_seconds: int = Field(
        default=60,
        env="REQUEST_TIMEOUT_SECONDS",
        description="Timeout for external API requests"
    )
    
    # Health check configuration
    health_check_timeout_seconds: int = Field(
        default=30,
        env="HEALTH_CHECK_TIMEOUT_SECONDS",
        description="Timeout for container health checks"
    )
    health_check_max_retries: int = Field(
        default=5,
        env="HEALTH_CHECK_MAX_RETRIES",
        description="Maximum retry attempts for health checks"
    )
    health_check_retry_interval: int = Field(
        default=5,
        env="HEALTH_CHECK_RETRY_INTERVAL",
        description="Interval in seconds between health check retries"
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


def get_settings() -> Settings:
    """
    Get application settings instance.
    
    Returns:
        Settings: Application settings configured from environment
    """
    return Settings()


def validate_settings(settings: Settings) -> bool:
    """
    Validate critical settings at startup.
    
    Args:
        settings: Settings instance to validate
        
    Returns:
        bool: True if all validations pass
        
    Raises:
        ValueError: If any critical setting is invalid
    """
    errors = []
    
    # Validate Ollama endpoint
    if not settings.ollama_endpoint.startswith(("http://", "https://")):
        errors.append(f"Invalid Ollama endpoint: {settings.ollama_endpoint}")
    
    # Validate temperature range
    if not 0.0 <= settings.ollama_temperature <= 1.0:
        errors.append(f"Ollama temperature must be between 0.0 and 1.0, got {settings.ollama_temperature}")
    
    # Validate timeout values
    if settings.ollama_timeout_seconds < 10:
        errors.append("Ollama timeout must be at least 10 seconds")
    
    # Validate retry counts
    if settings.max_pipeline_retries < 1:
        errors.append("Max retries must be at least 1")
    
    # Validate log level
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if settings.log_level not in valid_log_levels:
        errors.append(f"Invalid log level: {settings.log_level}")
    
    if errors:
        raise ValueError("Settings validation failed:\n" + "\n".join(errors))
    
    return True


# Default environment variable examples (can be placed in .env)
DEFAULT_ENV_EXAMPLE = """
# Application Configuration
APP_NAME=DevOps Pipeline Orchestrator
APP_VERSION=1.0.0
DEBUG=false
LOG_LEVEL=INFO

# Ollama Configuration (SSH Reverse Tunnel)
OLLAMA_ENDPOINT=http://127.0.0.1:11434
OLLAMA_MODEL=deepseek-coder:6.7b
OLLAMA_TEMPERATURE=0.2
OLLAMA_TIMEOUT_SECONDS=300

# Workspace Configuration
WORKSPACE_ROOT=/tmp/devops_pipeline

# Pipeline Configuration
MAX_PIPELINE_RETRIES=3
PIPELINE_TIMEOUT_SECONDS=1800

# Security Configuration
ENABLE_CLEANUP_ON_SUCCESS=true
ENABLE_CLEANUP_ON_FAILURE=false
SECURE_CREDENTIAL_HANDLING=true

# Health Check Configuration
HEALTH_CHECK_TIMEOUT_SECONDS=30
HEALTH_CHECK_MAX_RETRIES=5
HEALTH_CHECK_RETRY_INTERVAL=5
"""
