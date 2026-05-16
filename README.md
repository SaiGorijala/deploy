# DevOps Pipeline Orchestrator - Self-Healing Deployment Platform

A production-ready Python FastAPI application that orchestrates multi-stage deployment pipelines with **AI-powered autonomous error remediation**. When any pipeline stage fails, an embedded AI agent (powered by Ollama DeepSeek) automatically analyzes errors, generates fixes, and retries—dramatically reducing manual debugging.

## 🚀 Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Application                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │   REST API   │→ │  Pipeline    │→ │  Stage Handlers    │   │
│  │   Endpoints  │  │ Orchestrator │  │                    │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│                           │                    │                │
│                           ↓                    ↓                │
│                    ┌──────────────────────────────┐             │
│                    │   Self-Healing Loop          │             │
│                    │   (AI Agent + Retry Logic)   │             │
│                    └──────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ↓
                 ┌──────────────────────┐
                 │ SSH Reverse Tunnel   │
                 │ to Local Ollama      │
                 │ (127.0.0.1:11434)   │
                 └──────────────────────┘
```

## 📋 Pipeline Stages

1. **Git Clone** - Authenticated repository pulling
2. **SonarQube Analysis** - Code quality metrics
3. **Docker Build** - Container image compilation
4. **Docker Push** - Registry deployment
5. **Trivy Scan** - Vulnerability detection
6. **Remote Deploy** - SSH-based container deployment
7. **Health Check** - Service validation

## 🔧 Prerequisites

### System Requirements
- Python 3.9+
- Docker (with CLI access)
- Paramiko (for SSH operations)
- SonarQube instance (for code quality)
- Trivy CLI (for vulnerability scanning)
- Ollama running locally (for AI fixes)

### Installation

```bash
# Clone or create project directory
mkdir devops-pipeline && cd devops-pipeline

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn pydantic httpx paramiko

# Optional: Install Ollama (for local AI fixes)
# Visit: https://ollama.ai

# Install pipeline dependencies
pip install sonarqube-community-build
```

### Docker and Tools

```bash
# Install Docker
# https://docs.docker.com/get-docker/

# Install Trivy
# https://github.com/aquasecurity/trivy

# Install SonarQube (optional, for local development)
# Docker image: docker pull sonarqube
```

## 🌐 SSH Reverse Tunnel Setup

The application communicates with a local Ollama instance via SSH reverse tunnel. This allows secure, isolated AI processing.

### 1. On Your Local Machine (with Ollama)

```bash
# Start Ollama service
ollama serve

# In another terminal, pull the DeepSeek model
ollama pull deepseek-coder:6.7b

# Verify it's running
curl http://127.0.0.1:11434/api/tags
```

### 2. Establish SSH Reverse Tunnel from Cloud Server

From the cloud server running the FastAPI application:

```bash
# Forward remote localhost:11434 to local Ollama
ssh -R 11434:127.0.0.1:11434 -N -f your_local_machine

# Verify tunnel is active
curl http://127.0.0.1:11434/api/tags
```

Alternatively, add to `/etc/ssh/sshd_config`:

```
AllowStreamLocalForwarding yes
AllowTcpForwarding yes
```

Then establish the tunnel:

```bash
ssh -i /path/to/key.pem -R 11434:127.0.0.1:11434 user@cloud-server
```

## 📦 Project Structure

```
project/
├── app.py                      # FastAPI main application
├── models.py                   # Pydantic schemas
├── config.py                   # Configuration management
├── pipeline.py                 # Core orchestrator
├── ai_agent.py                 # DeepSeek AI integration
├── stages/
│   ├── __init__.py
│   ├── git_handler.py          # Repository cloning
│   ├── sonarqube_handler.py    # Code quality analysis
│   ├── docker_handler.py       # Container building
│   ├── trivy_handler.py        # Vulnerability scanning
│   └── deploy_handler.py       # Remote SSH deployment
├── .env                        # Environment configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## ⚙️ Configuration

### Environment Variables (`.env`)

```env
# Application
APP_NAME=DevOps Pipeline Orchestrator
DEBUG=false
LOG_LEVEL=INFO

# Ollama Configuration (SSH Reverse Tunnel)
OLLAMA_ENDPOINT=http://127.0.0.1:11434
OLLAMA_MODEL=deepseek-coder:6.7b
OLLAMA_TEMPERATURE=0.2
OLLAMA_TIMEOUT_SECONDS=300

# Workspace
WORKSPACE_ROOT=/tmp/devops_pipeline

# Pipeline
MAX_PIPELINE_RETRIES=3
PIPELINE_TIMEOUT_SECONDS=1800

# Security
ENABLE_CLEANUP_ON_SUCCESS=true
SECURE_CREDENTIAL_HANDLING=true

# Health Check
HEALTH_CHECK_TIMEOUT_SECONDS=30
HEALTH_CHECK_MAX_RETRIES=5
```

## 🚀 Running the Application

### Development

```bash
# Load environment
source venv/bin/activate
export $(cat .env | xargs)

# Run FastAPI application
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Production

```bash
# Using Gunicorn
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app:app --bind 0.0.0.0:8000
```

## 📡 API Reference

### Health Check

```bash
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-05-16T10:30:00.000000",
  "version": "1.0.0"
}
```

### List Deployments

```bash
GET /api/deployments
```

**Response:**
```json
{
  "deployments": [
    {
      "deployment_id": "uuid",
      "status": "COMPLETED",
      "created_at": "2024-05-16T10:00:00.000000",
      "pipeline_stage": "health_check",
      "git_repo": "https://github.com/user/repo"
    }
  ],
  "total": 1
}
```

### Get Deployment Status

```bash
GET /api/deployments/{deployment_id}
```

**Response:**
```json
{
  "deployment_id": "uuid",
  "status": "RUNNING",
  "current_stage": "docker_push",
  "logs": [
    "[INFO] Executing stage: git_clone",
    "[INFO] Repository cloned successfully"
  ],
  "ai_fixes": []
}
```

### Initiate Deployment

```bash
POST /api/deploy
Content-Type: application/json
```

**Request Body:**
```json
{
  "deployment_name": "my-service-v1",
  "git": {
    "git_repo_url": "https://github.com/user/repo.git",
    "git_username": "user",
    "git_token": "ghp_xxxxxxxxx"
  },
  "target_server": {
    "target_server_ip": "203.0.113.42",
    "target_server_username": "ubuntu",
    "target_server_pem_file_content": "-----BEGIN RSA PRIVATE KEY-----\n...",
    "target_server_port": 22
  },
  "docker": {
    "docker_hub_username": "user",
    "docker_hub_token": "dckr_xxxxxxxxx",
    "docker_image_name": "user/my-service",
    "docker_registry_url": "docker.io"
  },
  "sonarqube": {
    "sonar_host_url": "http://sonarqube.example.com:9000",
    "sonar_token": "squ_xxxxxxxxx",
    "sonar_project_key": "my-service"
  },
  "container_port": 8080,
  "container_health_check_path": "/health",
  "ai_agent": {
    "max_retries": 3
  }
}
```

**Response:**
```json
{
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "message": "Deployment pipeline queued. Check status at /api/deployments/{deployment_id}",
  "initiated_at": "2024-05-16T10:30:00.000000"
}
```

## 🤖 AI Self-Healing Features

### How It Works

When a pipeline stage fails:

1. **Error Interception** - Exception is caught with full context
2. **AI Analysis** - Error logs and file content sent to DeepSeek
3. **Fix Generation** - AI generates corrected configuration/code
4. **Validation** - Response parsed and validated
5. **Application** - Fix applied to workspace
6. **Retry** - Stage re-executed with corrected files

### Example: Dockerfile Fix

**Original Error:**
```
Step 1/5 : FROM node:latest
---> Pulling from library/node
ERROR: manifest not found
```

**AI Generated Fix:**
```dockerfile
FROM node:18-alpine  # More reliable base image
WORKDIR /app
COPY . .
RUN npm install
CMD ["npm", "start"]
```

### Prompt Engineering Strategy

DeepSeek is instructed to:
- Output **only** corrected file contents
- Use markdown code blocks (```lang)
- Provide zero explanations
- Generate production-ready code

## 📊 Output Metrics

Upon completion, deployment returns comprehensive tracking:

```json
{
  "sonarqube": {
    "project_key": "devops_my_service",
    "quality_gate_status": "PASSED",
    "bugs": 2,
    "vulnerabilities": 0,
    "code_smells": 5,
    "coverage": 78.5,
    "dashboard_url": "http://sonarqube.example.com:9000/dashboard?id=..."
  },
  "trivy": {
    "critical": 0,
    "high": 1,
    "medium": 3,
    "low": 7,
    "timestamp": "2024-05-16T10:45:00.000000",
    "report_url": "..."
  },
  "deployment": {
    "docker_hub_image_uri": "docker.io/user/my-service:20240516_104500",
    "target_server_ip": "203.0.113.42",
    "application_port": 8080,
    "container_id": "a1b2c3d4e5f6...",
    "validation_url": "http://203.0.113.42:8080/health"
  },
  "ai_fixes": [
    {
      "stage": "docker_build",
      "error": "manifest not found for node:latest",
      "fix_applied": "Changed base image to node:18-alpine",
      "retry_attempt": 1,
      "timestamp": "2024-05-16T10:35:00.000000"
    }
  ]
}
```

## 🔐 Security Considerations

### Credential Handling

- SSH private keys written to secure temporary files (perms: `0600`)
- Credentials cleared from memory after use
- No credentials logged or stored in deployment records
- HTTPS recommended for production API

### Network Security

- SSH reverse tunnel for Ollama communication
- Paramiko for secure SSH connections
- CORS configured for frontend access
- Rate limiting recommended for production

### Code Safety

- Subprocess calls use `check=True` for safety
- File permissions enforced (600 for SSH keys)
- Workspace isolation per deployment
- Automatic cleanup of temporary files

## 🛠️ Troubleshooting

### Ollama Connection Issues

```bash
# Verify tunnel is active
curl http://127.0.0.1:11434/api/tags

# Check reverse tunnel status
ps aux | grep ssh
# Should show: ssh -R 11434:...

# Restart tunnel if needed
ssh -R 11434:127.0.0.1:11434 user@cloud-server -N
```

### SonarQube Analysis Hangs

```bash
# Check SonarQube API
curl -H "Authorization: Bearer $SONAR_TOKEN" \
  http://sonarqube.example.com:9000/api/ce/activity

# Review polling configuration
grep SONARQUBE .env
```

### Docker Build Failures

```bash
# Test Docker locally
docker build -t test-image .

# Check Docker daemon
docker ps

# Verify credentials
docker login docker.io
```

### SSH Connection Errors

```bash
# Test SSH connectivity
ssh -i /path/to/key.pem ubuntu@203.0.113.42 "docker ps"

# Verify PEM key permissions
ls -la /path/to/key.pem  # Should be 600

# Check server firewall
# Ensure port 22 is accessible
```

## 📈 Monitoring & Logging

### Application Logs

```bash
# View logs in real-time
tail -f /var/log/devops-pipeline.log

# Filter by level
grep "ERROR" /var/log/devops-pipeline.log
grep "AI" /var/log/devops-pipeline.log
```

### Deployment Logs via API

```bash
# Get live logs for deployment
curl http://localhost:8000/api/deployments/{deployment_id}
```

### Metrics & Analytics

Track over time:
- Success/failure rates per stage
- AI fix effectiveness
- Average retry counts
- Time to deployment
- Security findings per scan

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy with DevOps Pipeline

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Trigger DevOps Pipeline
        run: |
          curl -X POST http://your-api-server:8000/api/deploy \
            -H "Content-Type: application/json" \
            -d @deployment-config.json
```

## 📄 License

This project is provided as-is for educational and production use.

## 🤝 Contributing

Contributions welcome! Areas for enhancement:
- Additional pipeline stages (Kubernetes, Terraform)
- Advanced AI prompt optimization
- Metrics dashboard
- Web UI for deployment management
- Webhook integrations

## 📞 Support

For issues or questions:
1. Check troubleshooting section above
2. Review logs for specific errors
3. Verify all prerequisites are installed
4. Test individual components in isolation

---

**Built with ❤️ for DevOps Automation**
