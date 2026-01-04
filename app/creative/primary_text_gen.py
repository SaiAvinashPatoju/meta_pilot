"""
Primary Text Generator - Creative Studio.
Generates ad body copy using Problem-Agitation-Solution framework.
"""
from typing import List, Optional
from google import genai
from pydantic import BaseModel
from app.config import settings


class PrimaryTextResult(BaseModel):
    """Result of primary text generation."""
    variations: List[str]
    framework: str = "PAS"  # Problem-Agitation-Solution
    rule_citations: List[str] = ["COPY-004"]


class PrimaryTextGenerator:
    """
    Generates primary text (body copy) per Jim's methodology.
    
    Rules:
    - [COPY-004] Use Problem-Agitation-Solution (PAS) framework
    """
    
    SYSTEM_PROMPT = """You are an expert Meta Ads copywriter trained on Jim's Digital Marketing methodology.

Your task is to write PRIMARY TEXT (body copy) for Facebook/Instagram ads.

USE THE PAS FRAMEWORK [COPY-004]:
1. PROBLEM: Identify the pain point your audience feels
2. AGITATION: Amplify the problem, make them feel it
3. SOLUTION: Present your product as the perfect solution

STRUCTURE:
- Hook (first line must stop the scroll)
- Problem statement
- Agitation (2-3 sentences)
- Solution introduction
- Call to action

FORMATTING:
- Use short paragraphs (1-2 sentences each)
- Add line breaks between sections
- Use emojis sparingly for visual breaks
- Keep under 500 characters for best performance

OUTPUT: One complete primary text, ready to use."""

    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.llm_model
    
    def generate(
        self, 
        product_name: str,
        usp: str,
        target_audience: Optional[str] = None,
        pain_points: Optional[List[str]] = None,
        count: int = 3
    ) -> PrimaryTextResult:
        """
        Generate primary text variations.
        
        Args:
            product_name: Name of the product/service
            usp: Unique Selling Proposition
            target_audience: Description of target audience
            pain_points: List of customer pain points
            count: Number of variations to generate
            
        Returns:
            PrimaryTextResult with copy variations
        """
        pain_text = ""
        if pain_points:
            pain_text = f"\nCUSTOMER PAIN POINTS:\n" + "\n".join(f"- {p}" for p in pain_points)
        
        user_prompt = f"""Write {count} PRIMARY TEXT variations for:

PRODUCT: {product_name}
USP: {usp}
TARGET AUDIENCE: {target_audience or 'Not specified'}{pain_text}

Generate {count} different versions, each using the PAS framework.
Separate each version with "---" on its own line."""

        full_prompt = f"{self.SYSTEM_PROMPT}\n\n{user_prompt}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config={
                "temperature": 0.8,
                "max_output_tokens": 1500
            }
        )
        
        # Parse variations (separated by ---)
        raw_output = response.text
        variations = [
            v.strip() 
            for v in raw_output.split("---") 
            if v.strip()
        ][:count]
        
        return PrimaryTextResult(
            variations=variations,
            framework="PAS",
            rule_citations=["COPY-004"]
        )
    
    def generate_hooks(self, product_name: str, usp: str, count: int = 5) -> List[str]:
        """Generate hook variations (first lines) for testing."""
        user_prompt = f"""Generate {count} HOOK lines for a Meta ad about:

PRODUCT: {product_name}
USP: {usp}

A hook is the FIRST LINE of the ad that stops the scroll.
Each hook should be under 100 characters.
Output one hook per line, no numbering."""

        system_prompt = "You write scroll-stopping first lines for Facebook ads."
        full_prompt = f"{system_prompt}\n\n{user_prompt}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=full_prompt,
            config={
                "temperature": 0.9,
                "max_output_tokens": 300
            }
        )
        
        hooks = [
            line.strip().lstrip("1234567890.-) ")
            for line in response.text.strip().split("\n")
            if line.strip()
        ][:count]
        
        return hooks


# Singleton
_generator: Optional[PrimaryTextGenerator] = None


def get_primary_text_generator() -> PrimaryTextGenerator:
    global _generator
    if _generator is None:
        _generator = PrimaryTextGenerator()
    return _generator
