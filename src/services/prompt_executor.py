# src/services/prompt_executor.py
from typing import Dict, Any
from services.cohere_client import CohereClient
from models import ExecutionResult
import json
import time

class PromptExecutor:
    def __init__(self, cohere_client: CohereClient):
        self.cohere_client = cohere_client
    
    def execute_prompt(self, prompt: str, temperature: float = 0.1) -> ExecutionResult:
        start_time = time.time()
        
        try:
            response = self.cohere_client.execute_web_search_prompt(prompt, temperature)
            execution_time = time.time() - start_time
            
            # Try to parse the response text as JSON if it looks like JSON
            parsed_json = None
            response_text = response.get("text", "")
            
            if response_text.strip().startswith("{") and response_text.strip().endswith("}"):
                try:
                    parsed_json = json.loads(response_text)
                except json.JSONDecodeError:
                    parsed_json = None
            
            return ExecutionResult(
                prompt=prompt,
                raw_response=response,
                response_text=response_text,
                parsed_json=parsed_json,
                execution_time=execution_time,
                success=True,
                error_message=None
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            return ExecutionResult(
                prompt=prompt,
                raw_response={},
                response_text="",
                parsed_json=None,
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )