"""
Trivy handler for container vulnerability scanning.
Manages image scanning, vulnerability parsing, and report generation.
"""

import subprocess
import logging
import json
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

from models import TrivyConfig, VulnerabilitySummary
from config import Settings

logger = logging.getLogger(__name__)


class TrivyHandler:
    """Handles Trivy vulnerability scanning."""
    
    def __init__(
        self,
        settings: Settings,
        config: TrivyConfig
    ):
        """
        Initialize Trivy handler.
        
        Args:
            settings: Application settings
            config: Trivy configuration
        """
        self.settings = settings
        self.config = config
        
        logger.info("TrivyHandler initialized")
    
    async def scan(self, image_uri: str) -> VulnerabilitySummary:
        """
        Scan Docker image for vulnerabilities.
        
        Args:
            image_uri: Full Docker image URI
            
        Returns:
            VulnerabilitySummary with vulnerability counts by severity
            
        Raises:
            Exception: If scan fails
        """
        logger.info(f"Starting Trivy scan for image: {image_uri}")
        
        try:
            # Run trivy scan with JSON output
            scan_results = self._run_trivy_scan(image_uri)
            
            # Parse results
            summary = self._parse_scan_results(scan_results)
            
            # Check severity threshold
            self._check_severity_threshold(summary)
            
            logger.info(f"Trivy scan completed for {image_uri}")
            return summary
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Trivy scan failed: {error_msg}")
            raise Exception(f"Trivy scan failed: {error_msg}")
        except Exception as e:
            logger.error(f"Error during vulnerability scanning: {str(e)}")
            raise
    
    def _run_trivy_scan(self, image_uri: str) -> Dict:
        """
        Execute Trivy scan and return JSON results.
        
        Args:
            image_uri: Docker image URI
            
        Returns:
            dict: Parsed JSON scan results
            
        Raises:
            subprocess.CalledProcessError: If trivy command fails
        """
        logger.info("Executing trivy scan command")
        
        # Build trivy command
        cmd = [
            "trivy",
            "image",
            "--format", "json",
            "--severity", "CRITICAL,HIGH,MEDIUM,LOW",
            "--exit-code", "0"  # Don't fail on vulnerabilities, we handle them
        ]
        
        # Add registry credentials if provided
        if self.config.trivy_username and self.config.trivy_token:
            cmd.extend([
                "--username", self.config.trivy_username,
                "--password", self.config.trivy_token
            ])
        
        cmd.append(image_uri)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )
            
            # Parse JSON output
            if result.stdout:
                return json.loads(result.stdout)
            else:
                logger.warning("Trivy returned no output")
                return {"Results": []}
                
        except FileNotFoundError:
            raise Exception(
                "Trivy not found. Please install Trivy: "
                "https://github.com/aquasecurity/trivy"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Trivy JSON output: {str(e)}")
            raise Exception(f"Invalid Trivy output format: {str(e)}")
        except subprocess.TimeoutExpired:
            raise Exception("Trivy scan timed out")
    
    def _parse_scan_results(self, results: Dict) -> VulnerabilitySummary:
        """
        Parse Trivy results and create vulnerability summary.
        
        Args:
            results: Trivy JSON scan results
            
        Returns:
            VulnerabilitySummary with counts by severity
        """
        logger.info("Parsing Trivy scan results")
        
        severity_counts = {
            "CRITICAL": 0,
            "HIGH": 0,
            "MEDIUM": 0,
            "LOW": 0
        }
        
        # Parse results from each target
        for result in results.get("Results", []):
            for vulnerability in result.get("Vulnerabilities", []):
                severity = vulnerability.get("Severity", "UNKNOWN")
                if severity in severity_counts:
                    severity_counts[severity] += 1
        
        logger.info(f"Vulnerability summary: {severity_counts}")
        
        return VulnerabilitySummary(
            critical=severity_counts["CRITICAL"],
            high=severity_counts["HIGH"],
            medium=severity_counts["MEDIUM"],
            low=severity_counts["LOW"],
            timestamp=datetime.utcnow().isoformat(),
            report_url=None  # Could be generated by storing results
        )
    
    def _check_severity_threshold(self, summary: VulnerabilitySummary):
        """
        Check if vulnerabilities exceed configured threshold.
        
        Args:
            summary: Vulnerability summary
            
        Raises:
            Exception: If threshold is exceeded
        """
        threshold = self.config.trivy_severity_threshold
        
        if threshold == "CRITICAL" and summary.critical > 0:
            raise Exception(f"CRITICAL vulnerabilities found: {summary.critical}")
        elif threshold == "HIGH" and (summary.critical > 0 or summary.high > 0):
            raise Exception(
                f"CRITICAL/HIGH vulnerabilities found: {summary.critical + summary.high}"
            )
        elif threshold == "MEDIUM" and (summary.critical > 0 or summary.high > 0 or summary.medium > 0):
            raise Exception(
                f"CRITICAL/HIGH/MEDIUM vulnerabilities found: {summary.critical + summary.high + summary.medium}"
            )
        
        logger.info(f"Vulnerability threshold check passed (threshold: {threshold})")
    
    def generate_report(self, summary: VulnerabilitySummary, output_path: Path) -> str:
        """
        Generate HTML report from vulnerability summary.
        
        Args:
            summary: Vulnerability summary
            output_path: Path to write report
            
        Returns:
            str: Path to generated report
        """
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trivy Vulnerability Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; }}
                .critical {{ color: #d32f2f; font-weight: bold; }}
                .high {{ color: #f57c00; font-weight: bold; }}
                .medium {{ color: #fbc02d; }}
                .low {{ color: #388e3c; }}
                h1 {{ color: #333; }}
            </style>
        </head>
        <body>
            <h1>Vulnerability Scan Report</h1>
            <div class=\"summary\">
                <p>Scan Timestamp: {summary.timestamp}</p>
                <p><span class=\"critical\">CRITICAL: {summary.critical}</span></p>
                <p><span class=\"high\">HIGH: {summary.high}</span></p>
                <p><span class=\"medium\">MEDIUM: {summary.medium}</span></p>
                <p><span class=\"low\">LOW: {summary.low}</span></p>
            </div>
        </body>
        </html>
        """
        
        with open(output_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"Generated vulnerability report at {output_path}")
        return str(output_path)
