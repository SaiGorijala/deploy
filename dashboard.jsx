import React, { useState, useEffect, useCallback } from 'react';

export default function DeploymentDashboard() {
  const [deployments, setDeployments] = useState([]);
  const [selectedDeployment, setSelectedDeployment] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    deployment_name: '',
    git_repo_url: '',
    git_username: '',
    git_token: '',
    target_server_ip: '',
    target_server_username: 'ubuntu',
    target_server_pem_file_content: '',
    docker_hub_username: '',
    docker_hub_token: '',
    docker_image_name: '',
    sonar_host_url: '',
    sonar_token: '',
    sonar_project_key: '',
    container_port: 8080,
    container_health_check_path: '/health',
  });
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState('all');
  const [liveUpdating, setLiveUpdating] = useState(null);

  const API_BASE = 'http://localhost:8000/api';

  // Fetch deployments
  const fetchDeployments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/deployments`);
      const data = await res.json();
      setDeployments(data.deployments || []);
    } catch (error) {
      console.error('Failed to fetch deployments:', error);
    }
  }, []);

  // Poll for status updates on selected deployment
  useEffect(() => {
    if (!selectedDeployment) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/deployments/${selectedDeployment.deployment_id}`);
        const data = await res.json();
        setSelectedDeployment(data);

        // Update in list
        setDeployments(prev =>
          prev.map(d => (d.deployment_id === selectedDeployment.deployment_id ? data : d))
        );
      } catch (error) {
        console.error('Failed to update deployment status:', error);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [selectedDeployment]);

  // Initial load
  useEffect(() => {
    fetchDeployments();
    const interval = setInterval(fetchDeployments, 5000);
    return () => clearInterval(interval);
  }, [fetchDeployments]);

  const handleSubmitDeployment = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const deploymentConfig = {
        deployment_name: formData.deployment_name,
        git: {
          git_repo_url: formData.git_repo_url,
          git_username: formData.git_username,
          git_token: formData.git_token,
        },
        target_server: {
          target_server_ip: formData.target_server_ip,
          target_server_username: formData.target_server_username,
          target_server_pem_file_content: formData.target_server_pem_file_content,
        },
        docker: {
          docker_hub_username: formData.docker_hub_username,
          docker_hub_token: formData.docker_hub_token,
          docker_image_name: formData.docker_image_name || undefined,
        },
        sonarqube: {
          sonar_host_url: formData.sonar_host_url,
          sonar_token: formData.sonar_token,
          sonar_project_key: formData.sonar_project_key || undefined,
        },
        container_port: parseInt(formData.container_port),
        container_health_check_path: formData.container_health_check_path,
      };

      const res = await fetch(`${API_BASE}/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deploymentConfig),
      });

      const data = await res.json();
      setSelectedDeployment({
        deployment_id: data.deployment_id,
        status: data.status,
        created_at: data.initiated_at,
        logs: [],
        ai_fixes: [],
      });
      setShowForm(false);
      setFormData({
        deployment_name: '',
        git_repo_url: '',
        git_username: '',
        git_token: '',
        target_server_ip: '',
        target_server_username: 'ubuntu',
        target_server_pem_file_content: '',
        docker_hub_username: '',
        docker_hub_token: '',
        docker_image_name: '',
        sonar_host_url: '',
        sonar_token: '',
        sonar_project_key: '',
        container_port: 8080,
        container_health_check_path: '/health',
      });
      fetchDeployments();
    } catch (error) {
      alert('Deployment submission failed: ' + error.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredDeployments = deployments.filter(d => {
    if (statusFilter === 'all') return true;
    return d.status.toLowerCase() === statusFilter.toLowerCase();
  });

  const getStatusColor = (status) => {
    switch (status?.toUpperCase()) {
      case 'COMPLETED':
        return '#10b981';
      case 'RUNNING':
      case 'INITIALIZING':
        return '#3b82f6';
      case 'FAILED':
        return '#ef4444';
      case 'QUEUED':
        return '#f59e0b';
      default:
        return '#6b7280';
    }
  };

  const getStageProgress = (stage) => {
    const stages = ['git_clone', 'sonarqube', 'docker_build', 'docker_push', 'trivy_scan', 'deploy', 'health_check'];
    return ((stages.indexOf(stage) + 1) / stages.length) * 100;
  };

  return (
    <div style={{
      fontFamily: '"Space Grotesk", "Courier New", monospace',
      background: 'linear-gradient(135deg, #0f172a 0%, #1a1f3a 50%, #0f172a 100%)',
      color: '#e2e8f0',
      minHeight: '100vh',
      padding: '0',
      margin: '0',
      overflow: 'auto'
    }}>
      {/* Header */}
      <div style={{
        background: 'rgba(15, 23, 42, 0.8)',
        borderBottom: '2px solid #00ff88',
        padding: '2rem',
        backdropFilter: 'blur(10px)',
        position: 'sticky',
        top: 0,
        zIndex: 100
      }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h1 style={{
                margin: '0',
                fontSize: '2.5rem',
                fontWeight: 700,
                color: '#00ff88',
                textShadow: '0 0 20px #00ff8844',
                letterSpacing: '2px'
              }}>
                ⚡ DEVOPS PIPELINE
              </h1>
              <p style={{
                margin: '0.5rem 0 0 0',
                color: '#94a3b8',
                fontSize: '0.9rem',
                textTransform: 'uppercase',
                letterSpacing: '1px'
              }}>
                Self-Healing Deployment Orchestrator
              </p>
            </div>
            <button
              onClick={() => setShowForm(!showForm)}
              style={{
                background: showForm ? '#ef4444' : '#00ff88',
                color: showForm ? '#fff' : '#000',
                border: 'none',
                padding: '12px 24px',
                borderRadius: '4px',
                fontSize: '1rem',
                fontWeight: 700,
                cursor: 'pointer',
                textTransform: 'uppercase',
                letterSpacing: '1px',
                boxShadow: showForm ? '0 0 20px #ef4444aa' : '0 0 20px #00ff8844',
                transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)'
              }}
            >
              {showForm ? '✕ Cancel' : '+ New Deployment'}
            </button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: '1400px', margin: '0 auto', padding: '2rem' }}>
        {/* Deployment Form */}
        {showForm && (
          <div style={{
            background: 'rgba(30, 41, 59, 0.6)',
            border: '2px solid #00ff88',
            borderRadius: '8px',
            padding: '2rem',
            marginBottom: '2rem',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 0 40px #00ff8833'
          }}>
            <h2 style={{
              color: '#00ff88',
              marginTop: 0,
              fontSize: '1.5rem',
              textTransform: 'uppercase',
              letterSpacing: '1px'
            }}>
              Configure Deployment
            </h2>

            <form onSubmit={handleSubmitDeployment} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              {/* Basic Info */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Deployment Name
                </label>
                <input
                  type="text"
                  value={formData.deployment_name}
                  onChange={(e) => setFormData({ ...formData, deployment_name: e.target.value })}
                  placeholder="e.g., production-v1"
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit',
                    transition: 'all 0.3s'
                  }}
                />
              </div>

              {/* Git Repo */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Git Repository URL
                </label>
                <input
                  type="text"
                  value={formData.git_repo_url}
                  onChange={(e) => setFormData({ ...formData, git_repo_url: e.target.value })}
                  placeholder="https://github.com/user/repo.git"
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* Git Username */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Git Username
                </label>
                <input
                  type="text"
                  value={formData.git_username}
                  onChange={(e) => setFormData({ ...formData, git_username: e.target.value })}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* Git Token */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Git Token (PAT)
                </label>
                <input
                  type="password"
                  value={formData.git_token}
                  onChange={(e) => setFormData({ ...formData, git_token: e.target.value })}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* Server IP */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Target Server IP
                </label>
                <input
                  type="text"
                  value={formData.target_server_ip}
                  onChange={(e) => setFormData({ ...formData, target_server_ip: e.target.value })}
                  placeholder="203.0.113.42"
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* Server Username */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Server Username
                </label>
                <input
                  type="text"
                  value={formData.target_server_username}
                  onChange={(e) => setFormData({ ...formData, target_server_username: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* PEM Key */}
              <div style={{ gridColumn: '1 / -1' }}>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  SSH Private Key (PEM)
                </label>
                <textarea
                  value={formData.target_server_pem_file_content}
                  onChange={(e) => setFormData({ ...formData, target_server_pem_file_content: e.target.value })}
                  placeholder="-----BEGIN RSA PRIVATE KEY-----..."
                  required
                  style={{
                    width: '100%',
                    height: '120px',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.85rem',
                    fontFamily: 'monospace',
                    resize: 'vertical'
                  }}
                />
              </div>

              {/* Docker Hub */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Docker Hub Username
                </label>
                <input
                  type="text"
                  value={formData.docker_hub_username}
                  onChange={(e) => setFormData({ ...formData, docker_hub_username: e.target.value })}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Docker Hub Token
                </label>
                <input
                  type="password"
                  value={formData.docker_hub_token}
                  onChange={(e) => setFormData({ ...formData, docker_hub_token: e.target.value })}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* SonarQube */}
              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  SonarQube URL
                </label>
                <input
                  type="text"
                  value={formData.sonar_host_url}
                  onChange={(e) => setFormData({ ...formData, sonar_host_url: e.target.value })}
                  placeholder="http://sonarqube.example.com:9000"
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  SonarQube Token
                </label>
                <input
                  type="password"
                  value={formData.sonar_token}
                  onChange={(e) => setFormData({ ...formData, sonar_token: e.target.value })}
                  required
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              <div>
                <label style={{ color: '#00ff88', display: 'block', marginBottom: '0.5rem', fontSize: '0.9rem', fontWeight: 600 }}>
                  Container Port
                </label>
                <input
                  type="number"
                  value={formData.container_port}
                  onChange={(e) => setFormData({ ...formData, container_port: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '12px',
                    background: 'rgba(15, 23, 42, 0.5)',
                    border: '1px solid #00ff88',
                    borderRadius: '4px',
                    color: '#e2e8f0',
                    fontSize: '0.95rem',
                    fontFamily: 'inherit'
                  }}
                />
              </div>

              {/* Submit */}
              <button
                type="submit"
                disabled={loading}
                style={{
                  gridColumn: '1 / -1',
                  padding: '16px',
                  background: loading ? '#666' : '#00ff88',
                  color: '#000',
                  border: 'none',
                  borderRadius: '4px',
                  fontSize: '1.1rem',
                  fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                  boxShadow: '0 0 30px #00ff8866',
                  transition: 'all 0.3s'
                }}
              >
                {loading ? 'Submitting...' : '▶ Launch Deployment Pipeline'}
              </button>
            </form>
          </div>
        )}

        {/* Stats */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '1rem',
          marginBottom: '2rem'
        }}>
          {[
            { label: 'Total Deployments', value: deployments.length, color: '#00ff88' },
            { label: 'In Progress', value: deployments.filter(d => d.status === 'RUNNING' || d.status === 'INITIALIZING').length, color: '#3b82f6' },
            { label: 'Completed', value: deployments.filter(d => d.status === 'COMPLETED').length, color: '#10b981' },
            { label: 'Failed', value: deployments.filter(d => d.status === 'FAILED').length, color: '#ef4444' }
          ].map((stat, idx) => (
            <div key={idx} style={{
              background: 'rgba(30, 41, 59, 0.4)',
              border: `1px solid ${stat.color}`,
              borderRadius: '4px',
              padding: '1.5rem',
              textAlign: 'center',
              boxShadow: `0 0 20px ${stat.color}33`
            }}>
              <div style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                {stat.label}
              </div>
              <div style={{ fontSize: '2.5rem', fontWeight: 700, color: stat.color, textShadow: `0 0 10px ${stat.color}44` }}>
                {stat.value}
              </div>
            </div>
          ))}
        </div>

        {/* Filter Tabs */}
        <div style={{
          display: 'flex',
          gap: '1rem',
          marginBottom: '2rem',
          flexWrap: 'wrap'
        }}>
          {['all', 'running', 'completed', 'failed'].map(status => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              style={{
                padding: '10px 20px',
                background: statusFilter === status ? '#00ff88' : 'rgba(30, 41, 59, 0.4)',
                color: statusFilter === status ? '#000' : '#e2e8f0',
                border: `1px solid ${statusFilter === status ? '#00ff88' : '#00ff8844'}`,
                borderRadius: '4px',
                cursor: 'pointer',
                textTransform: 'uppercase',
                fontSize: '0.9rem',
                fontWeight: 600,
                letterSpacing: '0.5px',
                transition: 'all 0.3s'
              }}
            >
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </button>
          ))}
        </div>

        {/* Deployments List */}
        <div style={{ display: 'grid', gap: '1rem' }}>
          {filteredDeployments.map(deployment => (
            <div
              key={deployment.deployment_id}
              onClick={() => setSelectedDeployment(deployment)}
              style={{
                background: selectedDeployment?.deployment_id === deployment.deployment_id
                  ? 'rgba(0, 255, 136, 0.1)'
                  : 'rgba(30, 41, 59, 0.4)',
                border: selectedDeployment?.deployment_id === deployment.deployment_id
                  ? '2px solid #00ff88'
                  : '1px solid rgba(0, 255, 136, 0.3)',
                borderRadius: '8px',
                padding: '1.5rem',
                cursor: 'pointer',
                transition: 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
                boxShadow: selectedDeployment?.deployment_id === deployment.deployment_id
                  ? '0 0 40px #00ff8844'
                  : 'none'
              }}
            >
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: '1.5rem', alignItems: 'start' }}>
                <div>
                  <h3 style={{
                    margin: '0 0 0.5rem 0',
                    color: '#00ff88',
                    fontSize: '1.2rem',
                    fontWeight: 700
                  }}>
                    {deployment.git_repo || deployment.deployment_id}
                  </h3>
                  <p style={{
                    margin: '0 0 1rem 0',
                    color: '#94a3b8',
                    fontSize: '0.9rem'
                  }}>
                    Stage: <span style={{ color: '#00ff88', fontWeight: 600 }}>{deployment.pipeline_stage || 'unknown'}</span>
                  </p>
                  {deployment.status === 'RUNNING' && (
                    <div style={{
                      background: 'rgba(59, 130, 246, 0.2)',
                      border: '1px solid #3b82f6',
                      borderRadius: '4px',
                      height: '6px',
                      overflow: 'hidden'
                    }}>
                      <div style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #3b82f6, #00ff88)',
                        width: `${getStageProgress(deployment.pipeline_stage)}%`,
                        animation: 'pulse 1.5s infinite'
                      }} />
                    </div>
                  )}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{
                    display: 'inline-block',
                    padding: '8px 16px',
                    background: `${getStatusColor(deployment.status)}22`,
                    border: `2px solid ${getStatusColor(deployment.status)}`,
                    borderRadius: '4px',
                    color: getStatusColor(deployment.status),
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    fontSize: '0.85rem',
                    letterSpacing: '0.5px'
                  }}>
                    {deployment.status}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Selected Deployment Details */}
        {selectedDeployment && (
          <div style={{
            marginTop: '2rem',
            background: 'rgba(30, 41, 59, 0.6)',
            border: '2px solid #00ff88',
            borderRadius: '8px',
            padding: '2rem',
            backdropFilter: 'blur(10px)',
            boxShadow: '0 0 40px #00ff8833'
          }}>
            <h2 style={{
              color: '#00ff88',
              marginTop: 0,
              fontSize: '1.5rem',
              textTransform: 'uppercase',
              letterSpacing: '1px'
            }}>
              Deployment Details
            </h2>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
              <div>
                <h3 style={{ color: '#00ff88', marginTop: 0, fontSize: '1rem', textTransform: 'uppercase' }}>
                  Information
                </h3>
                <div style={{ fontSize: '0.95rem', lineHeight: '1.8' }}>
                  <p><span style={{ color: '#94a3b8' }}>ID:</span> <code style={{ color: '#00ff88' }}>{selectedDeployment.deployment_id?.substring(0, 8)}...</code></p>
                  <p><span style={{ color: '#94a3b8' }}>Status:</span> <span style={{ color: getStatusColor(selectedDeployment.status) }}>{selectedDeployment.status}</span></p>
                  <p><span style={{ color: '#94a3b8' }}>Stage:</span> <code>{selectedDeployment.current_stage}</code></p>
                  <p><span style={{ color: '#94a3b8' }}>Created:</span> {new Date(selectedDeployment.created_at).toLocaleString()}</p>
                </div>
              </div>

              {selectedDeployment.pipeline_result?.ai_fixes?.length > 0 && (
                <div>
                  <h3 style={{ color: '#00ff88', marginTop: 0, fontSize: '1rem', textTransform: 'uppercase' }}>
                    🤖 AI Fixes Applied
                  </h3>
                  {selectedDeployment.pipeline_result.ai_fixes.map((fix, idx) => (
                    <div key={idx} style={{
                      background: 'rgba(16, 185, 129, 0.1)',
                      border: '1px solid #10b981',
                      borderRadius: '4px',
                      padding: '0.75rem',
                      marginBottom: '0.75rem',
                      fontSize: '0.9rem'
                    }}>
                      <div style={{ color: '#10b981', fontWeight: 600 }}>{fix.stage} (Attempt {fix.retries})</div>
                      <div style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{fix.error?.substring(0, 60)}...</div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Logs */}
            <div>
              <h3 style={{ color: '#00ff88', fontSize: '1rem', textTransform: 'uppercase', marginBottom: '1rem' }}>
                Execution Logs
              </h3>
              <div style={{
                background: '#000',
                border: '1px solid #00ff88',
                borderRadius: '4px',
                padding: '1rem',
                maxHeight: '400px',
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.85rem'
              }}>
                {selectedDeployment.logs && selectedDeployment.logs.length > 0 ? (
                  selectedDeployment.logs.map((log, idx) => (
                    <div key={idx} style={{
                      color: log.includes('ERROR') ? '#ef4444' : log.includes('WARNING') ? '#f59e0b' : '#00ff88',
                      marginBottom: '0.25rem',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    }}>
                      {log}
                    </div>
                  ))
                ) : (
                  <div style={{ color: '#94a3b8' }}>No logs yet...</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;700&display=swap');
        
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.7; }
        }
        
        input:focus, textarea:focus {
          outline: none;
          box-shadow: 0 0 15px #00ff8844 !important;
          border-color: #00ff88 !important;
        }
        
        button:hover {
          transform: translateY(-2px);
        }
      `}</style>
    </div>
  );
}
