"""
Model Router for MetaPilot.
Routes different task types to appropriate LLM models.

Strategy:
- Intake/clarification: Gemini Flash (fast, cheap)
- Copywriting: Gemini Pro (quality)
- Reasoning/analysis: Gemini Pro (accuracy)
- Response formatting: Gemini Flash (fast)
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from google import genai

from app.config import settings


class TaskType(str, Enum):
    """Types of tasks that can be routed to different models."""
    INTAKE = "intake"              # Validating inputs, clarification
    COPYWRITING = "copywriting"    # Generating ad copy, headlines
    ANALYSIS = "analysis"          # Performance analysis, reasoning
    STRATEGY = "strategy"          # Campaign strategy decisions
    FORMATTING = "formatting"      # Formatting responses
    SUMMARIZATION = "summarization"  # Summarizing content
    EXTRACTION = "extraction"      # Extracting info from text


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_name: str
    temperature: float
    max_output_tokens: int
    top_p: float = 0.95
    top_k: int = 40
    
    def to_config(self) -> Dict[str, Any]:
        """Convert to Gemini config dict."""
        return {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "top_p": self.top_p,
        }


class ModelRouter:
    """
    Routes tasks to appropriate LLM models based on task type.
    
    This ensures:
    - Quality tasks (copy, analysis) use higher-quality models
    - Simple tasks (intake, formatting) use faster, cheaper models
    - Each task type has optimized parameters
    """
    
    # Model configurations per task type
    TASK_CONFIGS: Dict[TaskType, ModelConfig] = {
        TaskType.INTAKE: ModelConfig(
            model_name="gemini-2.0-flash",  # Fast, good for validation
            temperature=0.3,  # Low creativity for accuracy
            max_output_tokens=500,
        ),
        TaskType.COPYWRITING: ModelConfig(
            model_name="gemini-2.0-flash",  # Quality for creative work
            temperature=0.7,  # Higher creativity
            max_output_tokens=1000,
        ),
        TaskType.ANALYSIS: ModelConfig(
            model_name="gemini-2.0-flash",  # Accuracy for analysis
            temperature=0.2,  # Very low for consistency
            max_output_tokens=1500,
        ),
        TaskType.STRATEGY: ModelConfig(
            model_name="gemini-2.0-flash",  # Reasoning quality
            temperature=0.3,
            max_output_tokens=1500,
        ),
        TaskType.FORMATTING: ModelConfig(
            model_name="gemini-2.0-flash",  # Fast for formatting
            temperature=0.1,
            max_output_tokens=2000,
        ),
        TaskType.SUMMARIZATION: ModelConfig(
            model_name="gemini-2.0-flash",  # Fast summarization
            temperature=0.2,
            max_output_tokens=500,
        ),
        TaskType.EXTRACTION: ModelConfig(
            model_name="gemini-2.0-flash",  # Accuracy for extraction
            temperature=0.1,  # Very low for deterministic output
            max_output_tokens=500,
        ),
    }
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize with Gemini API key."""
        self.api_key = api_key or settings.gemini_api_key
        self.client = genai.Client(api_key=self.api_key)
        self._call_count: Dict[TaskType, int] = {t: 0 for t in TaskType}
    
    def get_config(self, task_type: TaskType) -> ModelConfig:
        """Get the model configuration for a task type."""
        return self.TASK_CONFIGS.get(task_type, self.TASK_CONFIGS[TaskType.FORMATTING])
    
    def generate(
        self, 
        task_type: TaskType, 
        prompt: str,
        system_prompt: Optional[str] = None,
        override_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate content using the appropriate model for the task type.
        
        Args:
            task_type: The type of task to perform
            prompt: The user/content prompt
            system_prompt: Optional system instructions
            override_config: Optional config overrides
            
        Returns:
            Generated text response
        """
        config = self.get_config(task_type)
        
        # Build full prompt
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n"
        full_prompt += prompt
        
        # Merge config with overrides
        gen_config = config.to_config()
        if override_config:
            gen_config.update(override_config)
        
        try:
            response = self.client.models.generate_content(
                model=config.model_name,
                contents=full_prompt,
                config=gen_config
            )
            
            self._call_count[task_type] += 1
            return response.text
            
        except Exception as e:
            # Fallback to Flash model on error
            if config.model_name != "gemini-2.0-flash":
                return self._fallback_generate(prompt, system_prompt)
            raise e
    
    def _fallback_generate(
        self, 
        prompt: str, 
        system_prompt: Optional[str] = None
    ) -> str:
        """Fallback to Flash model if primary model fails."""
        full_prompt = ""
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n"
        full_prompt += prompt
        
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
            config={
                "temperature": 0.3,
                "max_output_tokens": 1000,
            }
        )
        return response.text
    
    def generate_with_retry(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        override_config: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate with automatic retry on failure."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return self.generate(
                    task_type=task_type,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    override_config=override_config
                )
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    continue
        
        raise last_error
    
    def batch_generate(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate multiple responses (sequentially for now).
        
        Args:
            tasks: List of dicts with 'task_type', 'prompt', 'system_prompt'
            
        Returns:
            List of generated responses
        """
        results = []
        for task in tasks:
            result = self.generate(
                task_type=task.get("task_type", TaskType.FORMATTING),
                prompt=task["prompt"],
                system_prompt=task.get("system_prompt"),
                override_config=task.get("override_config"),
            )
            results.append(result)
        return results
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get call counts by task type."""
        return {t.value: count for t, count in self._call_count.items()}
    
    def reset_stats(self) -> None:
        """Reset usage statistics."""
        self._call_count = {t: 0 for t in TaskType}


# Singleton instance
_model_router: Optional[ModelRouter] = None


def get_model_router() -> ModelRouter:
    """Get or create the model router singleton."""
    global _model_router
    if _model_router is None:
        _model_router = ModelRouter()
    return _model_router
