"""
FastAPI main application entry point for the DevOps Pipeline Orchestrator
Handles deployment requests, manages pipeline state, and coordinates all services.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from models import DeploymentRequest, DeploymentResponse, PipelineStatus
from pipeline import PipelineOrchestrator
from config import Settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="DevOps Pipeline Orchestrator",
    description="Self-healing deployment pipeline with AI-powered remediation",
    version="1.0.0"
)

# CORS configuration for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = Settings()

# Global state management
deployment_state: Dict[str, Any] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info("DevOps Pipeline Orchestrator starting...")
    logger.info(f"Ollama endpoint configured: {settings.ollama_endpoint}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on application shutdown."""
    logger.info("DevOps Pipeline Orchestrator shutting down...")


@app.get("/api/health")
async def health_check():
    """Health check endpoint for load balancers and monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/api/deployments")
async def list_deployments():
    """List all deployment executions with their current status."""
    return {
        "deployments": [
            {
                "deployment_id": dep_id,
                "status": state.get("status"),
                "created_at": state.get("created_at"),
                "completed_at": state.get("completed_at"),
                "pipeline_stage": state.get("current_stage"),
                "git_repo": state.get("git_repo_url")
            }
            for dep_id, state in deployment_state.items()
        ],
        "total": len(deployment_state)
    }


@app.get("/api/deployments/{deployment_id}")
async def get_deployment_status(deployment_id: str):
    """Get detailed status of a specific deployment."""
    if deployment_id not in deployment_state:
        raise HTTPException(status_code=404, detail="Deployment not found")
    
    state = deployment_state[deployment_id]
    return {
        "deployment_id": deployment_id,
        "status": state.get("status"),
        "created_at": state.get("created_at"),
        "current_stage": state.get("current_stage"),
        "logs": state.get("logs", []),
        "ai_fixes": state.get("ai_fixes", []),
        "pipeline_result": state.get("pipeline_result")
    }


@app.post("/api/deploy")
async def deploy(request: DeploymentRequest, background_tasks: BackgroundTasks):
    """
    Main deployment endpoint. Accepts credentials and configuration, 
    initiates the pipeline, and tracks execution in real-time.
    
    Args:
        request: DeploymentRequest with all required credentials
        background_tasks: FastAPI background task executor
        
    Returns:
        DeploymentResponse with deployment_id and initial status
    """
    deployment_id = str(uuid.uuid4())
    
    # Initialize deployment state
    deployment_state[deployment_id] = {
        "deployment_id": deployment_id,
        "status": "INITIALIZING",
        "created_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "current_stage": "git_clone",
        "logs": [],
        "ai_fixes": [],
        "pipeline_result": None
    }
    
    logger.info(f"New deployment initiated: {deployment_id}")
    
    # Add pipeline execution to background tasks
    background_tasks.add_task(
        execute_pipeline,
        deployment_id=deployment_id,
        request=request
    )
    
    return DeploymentResponse(
        deployment_id=deployment_id,
        status="QUEUED",
        message="Deployment pipeline queued. Check status at /api/deployments/{deployment_id}",
        initiated_at=datetime.utcnow().isoformat()
    )


async def execute_pipeline(deployment_id: str, request: DeploymentRequest):
    """
    Execute the complete deployment pipeline in background.
    
    Args:
        deployment_id: Unique deployment identifier
        request: Deployment request with credentials
    """
    try:
        # Initialize orchestrator
        orchestrator = PipelineOrchestrator(
            deployment_id=deployment_id,
            settings=settings,
            state_callback=lambda state: update_deployment_state(deployment_id, state)
        )
        
        # Execute pipeline
        result = await orchestrator.execute(request)
        
        # Update final state
        deployment_state[deployment_id].update({
            "status": "COMPLETED",
            "completed_at": datetime.utcnow().isoformat(),
            "pipeline_result": result.dict() if result else None
        })
        
        logger.info(f"Deployment {deployment_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Deployment {deployment_id} failed: {str(e)}")
        deployment_state[deployment_id].update({
            "status": "FAILED",
            "completed_at": datetime.utcnow().isoformat(),
            "error": str(e)
        })


def update_deployment_state(deployment_id: str, state_update: Dict[str, Any]):
    """
    Callback function to update deployment state from pipeline execution.
    
    Args:
        deployment_id: Deployment identifier
        state_update: Dictionary of state updates
    """
    if deployment_id in deployment_state:
        # Add to logs if present
        if "log" in state_update:
            deployment_state[deployment_id]["logs"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "message": state_update["log"]
            })
        
        # Add AI fixes if present
        if "ai_fix" in state_update:
            deployment_state[deployment_id]["ai_fixes"].append(state_update["ai_fix"])
        
        # Update other state fields
        for key, value in state_update.items():
            if key not in ["log", "ai_fix"]:
                deployment_state[deployment_id][key] = value


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
