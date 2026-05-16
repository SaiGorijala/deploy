"""
AI Agent module for autonomous error remediation using Ollama DeepSeek model.
Handles prompt engineering, API communication, response parsing, and fix application.
"""

import httpx
import logging
import re
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass

from config import Settings

logger = logging.getLogger(__name__)


class ParsingError(Exception):
    """Raised when AI response cannot be parsed correctly."""
    pass


@dataclass
class AIFixResult:
    """Result of AI-generated fix."""
    original_error: str
    fix_content: str
    file_type: str  # dockerfile, python, yaml, etc.
    applied_timestamp: str


class DeepSeekAgent:
    """
    AI agent using Ollama DeepSeek for autonomous error remediation.
    Handles prompt engineering, API calls, and response parsing.
    """
    
    SYSTEM_PROMPT = """You are an automated DevOps system agent specializing in infrastructure code remediation.
Your task is to analyze errors and generate corrected configuration or source files.

CRITICAL RULES:
1. Output ONLY the corrected file contents inside a single markdown code block.
2. Use the appropriate language identifier: ```dockerfile, ```python, ```yaml, ```json, etc.
3. Do NOT include any warnings, explanations, markdown text outside the code block, or preamble.
4. Do NOT include backticks inside the code block.
5. Generate production-ready, immediately usable code.
6. Include all necessary imports, dependencies, and configurations."""
    
    def __init__(self, settings: Settings):
        """
        Initialize the DeepSeek agent.
        
        Args:
            settings: Application settings with Ollama configuration
        """
        self.settings = settings
        self.endpoint = f"{settings.ollama_endpoint}/api/chat"
        self.model = settings.ollama_model
        self.temperature = settings.ollama_temperature
        self.timeout = httpx.Timeout(settings.ollama_timeout_seconds)
        
        logger.info(f"DeepSeekAgent initialized with endpoint: {self.endpoint}")
    
    async def analyze_and_fix(
        self,
        error_message: str,
        stage: str,
        error_logs: Optional[str] = None,
        file_content: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> AIFixResult:
        """
        Analyze error and generate fix using DeepSeek.
        
        Args:
            error_message: Primary error message
            stage: Pipeline stage where error occurred
            error_logs: Full error/execution logs
            file_content: Content of file that needs fixing
            file_type: Type of file (dockerfile, python, yaml, etc.)
            
        Returns:
            AIFixResult with generated fix
            
        Raises:
            ParsingError: If response cannot be parsed
            httpx.HTTPError: If Ollama API call fails
        """
        prompt = self._construct_prompt(
            error_message=error_message,
            stage=stage,
            error_logs=error_logs,
            file_content=file_content,
            file_type=file_type
        )
        
        logger.info(f"Requesting fix from DeepSeek for stage: {stage}")
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": self.temperature}
                    }
                )
                response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Ollama API error: {str(e)}")
            raise
        
        response_data = response.json()
        ai_response = response_data.get("message", {}).get("content", "")
        
        if not ai_response:
            logger.error("Empty response from DeepSeek")
            raise ParsingError("DeepSeek returned empty response")
        
        logger.info("Parsing DeepSeek response")
        fix_content, detected_type = self._parse_response(ai_response, file_type)
        
        return AIFixResult(
            original_error=error_message,
            fix_content=fix_content,
            file_type=detected_type,
            applied_timestamp=datetime.utcnow().isoformat()
        )
    
    def _construct_prompt(
        self,
        error_message: str,
        stage: str,
        error_logs: Optional[str] = None,
        file_content: Optional[str] = None,
        file_type: Optional[str] = None
    ) -> str:
        """
        Construct engineered prompt for DeepSeek.
        
        Args:
            error_message: Primary error
            stage: Pipeline stage
            error_logs: Full logs
            file_content: File that needs fixing
            file_type: File type identifier
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            f"Pipeline Stage: {stage}",
            f"Error: {error_message}",
            ""
        ]
        
        if file_type:
            prompt_parts.append(f"File Type: {file_type}")
        
        if error_logs:
            prompt_parts.append("\nExecution Logs:")
            prompt_parts.append(error_logs[-2000:])  # Last 2000 chars of logs
        
        if file_content:
            prompt_parts.append("\nCurrent File Content:")
            prompt_parts.append(file_content[-2000:])  # Last 2000 chars
        
        prompt_parts.extend([
            "",
            "Generate the CORRECTED configuration/source file.",
            "Include ONLY the file content in a markdown code block with appropriate language identifier.",
            "No explanations, no warnings, no text outside the code block."
        ])
        
        return "\n".join(prompt_parts)
    
    def _parse_response(self, response: str, expected_type: Optional[str] = None) -> Tuple[str, str]:
        """
        Parse DeepSeek response to extract code block and file type.
        
        Priority 1: Extract standard markdown code blocks
        Priority 2: Fallback to line-by-line matching
        Priority 3: Raise ParsingError
        
        Args:
            response: Raw DeepSeek response
            expected_type: Expected file type hint
            
        Returns:
            Tuple of (code_content, detected_file_type)
            
        Raises:
            ParsingError: If response cannot be parsed
        """
        # Priority 1: Standard markdown code block extraction
        code_block_pattern = r'^```(\w+)?\n(.*?)\n```$'
        match = re.search(code_block_pattern, response, re.MULTILINE | re.DOTALL)
        
        if match:
            file_type = match.group(1) or expected_type or "txt"
            code_content = match.group(2)
            logger.info(f"Extracted code block: {file_type}")
            return code_content.strip(), file_type
        
        # Priority 2: Fallback parsing for common patterns
        fallback_patterns = {
            "dockerfile": [r"^FROM\s+", r"^RUN\s+", r"^WORKDIR\s+"],
            "python": [r"^import\s+", r"^from\s+.*import", r"^def\s+"],
            "yaml": [r"^[a-zA-Z_]+:\s*", r"^\s+-\s+"],
            "json": [r"^\{", r"^\["]
        }
        
        detected_type = expected_type or "txt"
        
        for file_type, patterns in fallback_patterns.items():
            if any(re.search(pattern, response, re.MULTILINE) for pattern in patterns):
                detected_type = file_type
                logger.info(f"Detected file type via fallback: {detected_type}")
                return response.strip(), detected_type
        
        # Priority 3: No valid pattern found
        logger.error(f"Failed to parse response: {response[:200]}")
        raise ParsingError(
            f"Could not extract valid code block from response. "
            f"Response should be in markdown format: ```language\\ncode\\n```"
        )
    
    async def validate_fix(self, fix_result: AIFixResult) -> bool:
        """
        Basic validation of generated fix.
        
        Args:
            fix_result: Generated fix to validate
            
        Returns:
            bool: True if fix appears valid
        """
        # Check that content is not empty
        if not fix_result.fix_content or len(fix_result.fix_content.strip()) == 0:
            logger.warning("Generated fix is empty")
            return False
        
        # Type-specific validations
        if fix_result.file_type == "dockerfile":
            if not re.search(r"^FROM\s+", fix_result.fix_content, re.MULTILINE):
                logger.warning("Dockerfile fix missing FROM statement")
                return False
        
        elif fix_result.file_type == "json":
            try:
                import json
                json.loads(fix_result.fix_content)
            except json.JSONDecodeError as e:
                logger.warning(f"Generated JSON is invalid: {str(e)}")
                return False
        
        elif fix_result.file_type == "yaml":
            try:
                import yaml
                yaml.safe_load(fix_result.fix_content)
            except Exception as e:
                logger.warning(f"Generated YAML is invalid: {str(e)}")
                return False
        
        logger.info("Fix validation passed")
        return True
    
    def _sanitize_response(self, response: str) -> str:
        """
        Sanitize response to remove unwanted characters.
        
        Args:
            response: Raw response string
            
        Returns:
            Sanitized response
        """
        # Remove markdown code fence escape sequences
        response = response.replace("\\n", "\n")
        response = response.replace("\\`", "`")
        return response.strip()


class FixApplicator:
    """Applies generated fixes to files in the workspace."""
    
    @staticmethod
    def apply_fix(
        fix_result: AIFixResult,
        target_file_path: str
    ) -> bool:
        """
        Apply generated fix to target file.
        
        Args:
            fix_result: AI-generated fix to apply
            target_file_path: Path to file to update
            
        Returns:
            bool: True if fix applied successfully
        """
        try:
            with open(target_file_path, 'w') as f:
                f.write(fix_result.fix_content)
            
            logger.info(f"Applied fix to {target_file_path}")
            return True
            
        except IOError as e:
            logger.error(f"Failed to write fix to {target_file_path}: {str(e)}")
            return False
    
    @staticmethod
    def backup_file(file_path: str) -> bool:
        """
        Create backup of file before applying fix.
        
        Args:
            file_path: Path to file to backup
            
        Returns:
            bool: True if backup created successfully
        """
        import shutil
        try:
            backup_path = f"{file_path}.backup"
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup {file_path}: {str(e)}")
            return False
