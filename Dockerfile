FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    openssh-client \
    unzip \
    lsb-release \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install SonarQube Scanner
RUN apt-get update && apt-get install -y \
    default-jre \
    && rm -rf /var/lib/apt/lists/*

RUN curl -o /tmp/sonar-scanner.zip https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip \
    && unzip -q /tmp/sonar-scanner.zip -d /opt \
    && rm /tmp/sonar-scanner.zip \
    && ln -s /opt/sonar-scanner-5.0.1.3006-linux/bin/sonar-scanner /usr/local/bin/sonar-scanner

# Install Trivy (vulnerability scanner)
RUN curl -fsSL https://aquasecurity.github.io/trivy-repo/deb/public.key | apt-key add - \
    && echo "deb https://aquasecurity.github.io/trivy-repo/deb $(lsb_release -sc) main" | tee /etc/apt/sources.list.d/trivy.list \
    && apt-get update && apt-get install -y trivy \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI (for building images inside container)
RUN curl -fsSL https://get.docker.com -o /tmp/get-docker.sh \
    && sh /tmp/get-docker.sh \
    && rm /tmp/get-docker.sh

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create workspace directory
RUN mkdir -p /tmp/devops_pipeline

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Expose API port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
