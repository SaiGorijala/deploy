"""
Pipeline orchestrator that coordinates all deployment stages with AI self-healing.
Implements the main execution flow and error handling/remediation loop.
"""

import logging
import asyncio
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
import shutil

from models import DeploymentRequest, PipelineResult, PipelineStage, AIFix
from config import Settings
from ai_agent import DeepSeekAgent, FixApplicator, ParsingError
from stages.git_handler import GitHandler
from stages.sonarqube_handler import SonarQubeHandler
from stages.docker_handler import DockerHandler
from stages.trivy_handler import TrivyHandler
from stages.deploy_handler import DeployHandler

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the complete deployment pipeline with AI self-healing capabilities.
    Manages stage execution, error handling, and fix application.
    """
    
    def __init__(
        self,
        deployment_id: str,
        settings: Settings,
        state_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Initialize pipeline orchestrator.
        
        Args:
            deployment_id: Unique deployment identifier
            settings: Application settings
            state_callback: Optional callback for state updates
        """
        self.deployment_id = deployment_id
        self.settings = settings
        self.state_callback = state_callback or self._default_callback
        
        # Create workspace for this deployment
        self.workspace_root = Path(settings.workspace_root) / deployment_id
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize AI agent
        self.ai_agent = DeepSeekAgent(settings)
        
        # Initialize handlers
        self.git_handler = None
        self.sonarqube_handler = None
        self.docker_handler = None
        self.trivy_handler = None
        self.deploy_handler = None
        
        # Execution tracking
        self.start_time = None
        self.end_time = None
        self.logs: List[str] = []
        self.ai_fixes: List[Dict[str, Any]] = []
        
        logger.info(f"Pipeline orchestrator initialized for deployment: {deployment_id}")
        logger.info(f"Workspace: {self.workspace_root}")
    
    async def execute(self, request: DeploymentRequest) -> Optional[PipelineResult]:
        """
        Execute the complete deployment pipeline.
        
        Args:
            request: Deployment request with all credentials
            
        Returns:
            PipelineResult with final metrics, or None if failed
        """
        self.start_time = datetime.utcnow()
        self._log(f"Starting deployment pipeline for {request.deployment_name or 'unnamed'}")
        self._update_state({"status": "RUNNING"})
        
        try:
            # Initialize handlers
            self.git_handler = GitHandler(self.settings, self.workspace_root, request.git)
            self.sonarqube_handler = SonarQubeHandler(self.settings, request.sonarqube)
            self.docker_handler = DockerHandler(self.settings, request.docker)
            self.trivy_handler = TrivyHandler(self.settings, request.trivy)
            self.deploy_handler = DeployHandler(self.settings, request.target_server)
            
            # Execute pipeline stages
            git_result = await self._execute_stage(
                stage=PipelineStage.GIT_CLONE,
                execute_fn=lambda: self.git_handler.clone_repository(),
                request=request
            )
            if not git_result:
                raise Exception("Git clone failed")
            
            repo_path = git_result
            
            # SonarQube analysis
            sonarqube_result = await self._execute_stage(
                stage=PipelineStage.SONARQUBE,
                execute_fn=lambda: self.sonarqube_handler.analyze(repo_path, request),
                request=request,
                context={"repo_path": repo_path}
            )
            
            # Docker build and push
            docker_result = await self._execute_stage(
                stage=PipelineStage.DOCKER_BUILD,
                execute_fn=lambda: self.docker_handler.build_and_push(repo_path, request),
                request=request,
                context={"repo_path": repo_path}
            )
            if not docker_result:
                raise Exception("Docker build/push failed")
            
            image_uri = docker_result
            
            # Trivy vulnerability scan
            trivy_result = await self._execute_stage(
                stage=PipelineStage.TRIVY_SCAN,
                execute_fn=lambda: self.trivy_handler.scan(image_uri),
                request=request,
                context={"image_uri": image_uri}
            )
            
            # Remote deployment
            deploy_result = await self._execute_stage(
                stage=PipelineStage.DEPLOY,
                execute_fn=lambda: self.deploy_handler.deploy(
                    image_uri=image_uri,
                    request=request
                ),
                request=request,
                context={"image_uri": image_uri}
            )
            if not deploy_result:
                raise Exception("Deployment failed")
            
            container_id, server_ip, port = deploy_result
            
            # Health check
            health_result = await self._execute_stage(
                stage=PipelineStage.HEALTH_CHECK,
                execute_fn=lambda: self.deploy_handler.health_check(
                    server_ip=server_ip,
                    port=port,
                    request=request
                ),
                request=request
            )
            
            # Build final result
            self.end_time = datetime.utcnow()
            duration = (self.end_time - self.start_time).total_seconds()
            
            result = PipelineResult(
                deployment_id=self.deployment_id,
                status="COMPLETED",
                created_at=self.start_time.isoformat(),
                completed_at=self.end_time.isoformat(),
                duration_seconds=duration,
                sonarqube=sonarqube_result,
                trivy=trivy_result,
                deployment=deploy_result if isinstance(deploy_result, dict) else None,
                ai_fixes=self.ai_fixes,
                logs=self.logs
            )
            
            self._log("Pipeline completed successfully")
            self._update_state({"status": "COMPLETED", "pipeline_result": result})
            
            return result
            
        except Exception as e:
            self.end_time = datetime.utcnow()
            self._log(f"Pipeline failed: {str(e)}", level="ERROR")
            self._update_state({"status": "FAILED", "error": str(e)})
            
            # Cleanup on failure if configured
            if not self.settings.enable_cleanup_on_failure:
                self._log(f"Workspace preserved for debugging at: {self.workspace_root}")
            else:
                await self._cleanup_workspace()
            
            raise
    
    async def _execute_stage(
        self,
        stage: PipelineStage,
        execute_fn: Callable,
        request: DeploymentRequest,
        context: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Execute a single pipeline stage with self-healing retry logic.
        
        Args:
            stage: Pipeline stage to execute
            execute_fn: Async function to execute
            request: Deployment request for error context
            context: Additional context for error analysis
            
        Returns:
            Stage execution result, or None if all retries exhausted
        """
        self._log(f"Executing stage: {stage.value}")
        self._update_state({"current_stage": stage.value})
        
        max_retries = request.ai_agent.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                result = await execute_fn()
                self._log(f"Stage {stage.value} completed successfully")
                return result
                
            except Exception as e:
                error_message = str(e)
                self._log(
                    f"Stage {stage.value} failed (attempt {attempt + 1}/{max_retries + 1}): {error_message}",
                    level="ERROR"
                )
                
                if attempt < max_retries:
                    # Attempt AI fix
                    fix_applied = await self._apply_ai_fix(
                        stage=stage,
                        error_message=error_message,
                        attempt=attempt,
                        context=context,
                        request=request
                    )
                    
                    if fix_applied:
                        self._log(f"Retrying stage {stage.value} after AI fix")
                        await asyncio.sleep(2)  # Brief delay before retry
                        continue
                
                # No more retries or fix failed
                raise
        
        return None
    
    async def _apply_ai_fix(
        self,
        stage: PipelineStage,
        error_message: str,
        attempt: int,
        context: Optional[Dict[str, Any]],
        request: DeploymentRequest
    ) -> bool:
        """
        Request AI fix for stage failure and apply it.
        
        Args:
            stage: Failed pipeline stage
            error_message: Error message from stage
            attempt: Attempt number
            context: Stage execution context
            request: Deployment request
            
        Returns:
            bool: True if fix was successfully applied
        """
        try:
            self._log(f"Requesting AI fix for {stage.value}")
            
            # Construct error context
            error_logs = "\n".join(self.logs[-10:])  # Last 10 log lines
            
            # Determine file type and content based on stage
            file_type = None
            file_content = None
            
            if stage == PipelineStage.DOCKER_BUILD and context and "repo_path" in context:
                file_type = "dockerfile"
                dockerfile_path = Path(context["repo_path"]) / "Dockerfile"
                if dockerfile_path.exists():
                    with open(dockerfile_path, 'r') as f:
                        file_content = f.read()
            
            # Request fix from DeepSeek
            fix_result = await self.ai_agent.analyze_and_fix(
                error_message=error_message,
                stage=stage.value,
                error_logs=error_logs,
                file_content=file_content,
                file_type=file_type
            )
            
            # Validate fix
            is_valid = await self.ai_agent.validate_fix(fix_result)
            if not is_valid:
                self._log("AI-generated fix failed validation", level="WARNING")
                return False
            
            # Apply fix to workspace
            if file_type == "dockerfile" and context and "repo_path" in context:
                target_file = Path(context["repo_path"]) / "Dockerfile"
                success = FixApplicator.apply_fix(fix_result, str(target_file))
                if success:
                    self._log(f"Applied AI fix to Dockerfile")
                    self.ai_fixes.append({
                        "stage": stage.value,
                        "error": error_message,
                        "fix_applied": fix_result.fix_content[:500],  # Store first 500 chars
                        "retries": attempt + 1,
                        "timestamp": fix_result.applied_timestamp
                    })
                    return True
            
            return False
            
        except ParsingError as e:
            self._log(f"AI response parsing failed: {str(e)}", level="WARNING")
            return False
        except Exception as e:
            self._log(f"AI fix request failed: {str(e)}", level="WARNING")
            return False
    
    def _log(self, message: str, level: str = "INFO"):
        """
        Log message and update state.
        
        Args:
            message: Log message
            level: Log level
        """
        log_entry = f"[{level}] {message}"
        self.logs.append(log_entry)
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)
        
        self._update_state({"log": log_entry})
    
    def _update_state(self, state_update: Dict[str, Any]):
        """Update pipeline state via callback."""
        if self.state_callback:
            self.state_callback(state_update)
    
    async def _cleanup_workspace(self):
        """Clean up temporary workspace after deployment."""
        try:
            if self.workspace_root.exists():
                shutil.rmtree(self.workspace_root)
                self._log(f"Cleaned up workspace: {self.workspace_root}")
        except Exception as e:
            self._log(f"Failed to cleanup workspace: {str(e)}", level="WARNING")
    
    def _default_callback(self, state_update: Dict[str, Any]):
        """Default state callback (no-op)."""
        pass
