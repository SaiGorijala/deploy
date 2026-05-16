# Quick Start Guide - DevOps Pipeline Orchestrator

## 🚀 5-Minute Setup

### Prerequisites
- Python 3.9+
- Docker & Docker CLI
- Git
- SSH key pair for target servers
- Ollama running locally (with DeepSeek model)

### Step 1: Clone & Install

```bash
# Create project directory
mkdir devops-pipeline && cd devops-pipeline

# Copy all provided files to this directory

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
```

### Step 2: Configure Ollama

```bash
# On your local machine, start Ollama
ollama serve

# In another terminal, pull the DeepSeek model
ollama pull deepseek-coder:6.7b

# Verify it's running
curl http://127.0.0.1:11434/api/tags
```

### Step 3: Setup SSH Reverse Tunnel

```bash
# From cloud server, establish reverse tunnel
ssh -R 11434:127.0.0.1:11434 -N -f your_local_machine

# Or use persistent tunnel with screen/tmux
screen -S ollama-tunnel
ssh -R 11434:127.0.0.1:11434 your_local_machine
# Press Ctrl+A then D to detach
```

### Step 4: Start FastAPI Application

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API is now running at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs` (Swagger UI)
- ReDoc: `http://localhost:8000/redoc`

### Step 5: Access Dashboard

Open the React dashboard (if integrated):
```bash
# In a new terminal, navigate to dashboard directory
cd dashboard

# Install React dependencies
npm install

# Start development server
npm start
```

Dashboard available at `http://localhost:3000`

---

## 📡 Preparing Credentials

### 1. Git Personal Access Token

**GitHub:**
1. Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Repository access: All repositories
3. Permissions: Contents (read), Metadata (read)
4. Copy token (e.g., `ghp_xxxxxxxxxxxxx`)

**GitLab:**
1. Settings → Access tokens
2. Scopes: api, read_repository
3. Copy token

### 2. Docker Hub Token

1. Account Settings → Security → Personal access tokens
2. Create token with Read/Write permissions
3. Copy token

### 3. SonarQube Token

1. User icon → My Account → Security → Tokens
2. Generate token
3. Copy token

### 4. SSH Private Key

```bash
# Generate key pair (if needed)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/deploy_key -N ""

# Get private key content
cat ~/.ssh/deploy_key
# Copy entire content including BEGIN and END lines
```

---

## 🔄 Testing the Pipeline

### Health Check

```bash
curl http://localhost:8000/api/health
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
curl http://localhost:8000/api/deployments
```

### Create Test Deployment

```bash
# Create a deployment request
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_name": "test-deployment",
    "git": {
      "git_repo_url": "https://github.com/your-repo.git",
      "git_username": "your-username",
      "git_token": "ghp_xxxxxxxxxxxxx"
    },
    "target_server": {
      "target_server_ip": "203.0.113.42",
      "target_server_username": "ubuntu",
      "target_server_pem_file_content": "-----BEGIN RSA PRIVATE KEY-----\n...\n-----END RSA PRIVATE KEY-----",
      "target_server_port": 22
    },
    "docker": {
      "docker_hub_username": "your-username",
      "docker_hub_token": "dckr_xxxxxxxxxxxxx",
      "docker_image_name": "your-username/your-app"
    },
    "sonarqube": {
      "sonar_host_url": "http://sonarqube.example.com:9000",
      "sonar_token": "squ_xxxxxxxxxxxxx"
    },
    "container_port": 8080,
    "container_health_check_path": "/health"
  }'
```

**Response:**
```json
{
  "deployment_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "message": "Deployment pipeline queued...",
  "initiated_at": "2024-05-16T10:30:00.000000"
}
```

### Monitor Deployment

```bash
# Get deployment status
curl http://localhost:8000/api/deployments/550e8400-e29b-41d4-a716-446655440000
```

---

## 🛠️ Troubleshooting

### Ollama Connection Fails

```bash
# Check tunnel is running
ps aux | grep "ssh -R 11434"

# Check Ollama is listening locally
curl http://127.0.0.1:11434/api/tags

# Restart tunnel
ssh -R 11434:127.0.0.1:11434 your_local_machine
```

### Docker Build Fails

```bash
# Test locally
cd /tmp/devops_pipeline/your-deployment-id/repository
docker build -t test .

# Check docker daemon
docker ps
```

### SSH Connection Refused

```bash
# Test SSH connection
ssh -i ~/.ssh/deploy_key ubuntu@203.0.113.42

# Check server is running
ping 203.0.113.42

# Verify SSH port
nmap -p 22 203.0.113.42
```

### SonarQube Analysis Timeout

1. Check SonarQube is running
2. Verify token is valid
3. Increase polling time in `.env`: `SONARQUBE_MAX_POLLING_ATTEMPTS=240`

---

## 📚 Example Deployments

### Simple Node.js App

```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_name": "node-app-v1",
    "git": {
      "git_repo_url": "https://github.com/user/node-app.git",
      "git_username": "user",
      "git_token": "ghp_xxxxxxxxxxxxx"
    },
    "target_server": {
      "target_server_ip": "203.0.113.42",
      "target_server_username": "ubuntu",
      "target_server_pem_file_content": "... PEM content ...",
      "target_server_port": 22
    },
    "docker": {
      "docker_hub_username": "user",
      "docker_hub_token": "dckr_xxxxxxxxxxxxx"
    },
    "sonarqube": {
      "sonar_host_url": "http://sonarqube.local:9000",
      "sonar_token": "squ_xxxxxxxxxxxxx"
    },
    "container_port": 3000,
    "container_health_check_path": "/api/health"
  }'
```

### Python Flask App

```bash
curl -X POST http://localhost:8000/api/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "deployment_name": "flask-api-v1",
    "git": {
      "git_repo_url": "https://github.com/user/flask-api.git",
      "git_username": "user",
      "git_token": "ghp_xxxxxxxxxxxxx"
    },
    "target_server": {
      "target_server_ip": "203.0.113.42",
      "target_server_username": "ubuntu",
      "target_server_pem_file_content": "... PEM content ...",
      "target_server_port": 22
    },
    "docker": {
      "docker_hub_username": "user",
      "docker_hub_token": "dckr_xxxxxxxxxxxxx"
    },
    "sonarqube": {
      "sonar_host_url": "http://sonarqube.local:9000",
      "sonar_token": "squ_xxxxxxxxxxxxx"
    },
    "container_port": 5000,
    "container_health_check_path": "/health"
  }'
```

---

## 🔐 Security Best Practices

1. **Secrets Management**
   - Never commit credentials to Git
   - Use environment variables or secret managers
   - Rotate tokens regularly

2. **SSH Keys**
   - Use separate keys for each deployment
   - Restrict key permissions: `chmod 600`
   - Rotate keys periodically

3. **Network Security**
   - Use SSH reverse tunnel for Ollama (not direct exposure)
   - Restrict SonarQube/Docker Hub to HTTPS
   - Enable firewall rules on target servers

4. **Credential Cleanup**
   - Application clears credentials from memory after use
   - Temporary SSH keys are securely deleted
   - Workspace files cleaned up on success

---

## 📊 Monitoring & Logs

### Application Logs

```bash
# View logs with timestamps
tail -f /tmp/devops_pipeline/*/logs.txt

# Filter by deployment ID
grep "deployment-id" /tmp/devops_pipeline/*/logs.txt

# Monitor pipeline stages
tail -f app.log | grep "stage"
```

### Deployment Metrics

Access via API:
```bash
curl http://localhost:8000/api/deployments/{deployment_id}
```

Returns:
- Pipeline status
- Execution logs
- AI fixes applied
- Quality metrics (SonarQube)
- Security findings (Trivy)

---

## 🚀 Production Deployment

### Using Gunicorn

```bash
pip install gunicorn

# Run with 4 workers
gunicorn -w 4 -k uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile - \
  app:app
```

### Using Docker

```bash
# Build image
docker build -t devops-pipeline:latest .

# Run container
docker run -d \
  --name devops-api \
  -p 8000:8000 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e OLLAMA_ENDPOINT=http://host.docker.internal:11434 \
  devops-pipeline:latest
```

### Using Kubernetes

```bash
# Apply Kubernetes manifests
kubectl apply -f k8s/devops-pipeline.yaml

# Check deployment
kubectl get pods -n devops-pipeline
kubectl logs -f -n devops-pipeline deployment/devops-api
```

---

## 📞 Support & Debugging

### Enable Debug Logging

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Access Swagger Documentation

Navigate to: `http://localhost:8000/docs`

### Check API Health

```bash
curl -v http://localhost:8000/api/health
```

### Reset Application State

```bash
# Clean workspace
rm -rf /tmp/devops_pipeline/*

# Restart application
pkill -f "uvicorn"
python -m uvicorn app:app --reload
```

---

**Happy Deploying! 🚀**
