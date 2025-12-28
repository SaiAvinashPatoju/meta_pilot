"""
Headline Generator - Creative Studio.
Generates ad headlines following Jim's copywriting rules.
"""
from typing import List, Optional
from openai import OpenAI
from pydantic import BaseModel, Field
from app.config import settings
from app.knowledge_base.rules import validate_headline_has_usp


class HeadlineResult(BaseModel):
    """Result of headline generation."""
    headlines: List[str]
    usp_keywords: List[str]
    validation: List[dict]
    rule_citations: List[str] = ["COPY-001"]


class HeadlineGenerator:
    """
    Generates ad headlines per Jim's methodology.
    
    Rules:
    - [COPY-001] Headlines must be concise and USP-focused
    - [COPY-003] Use different USP than description
    """
    
    SYSTEM_PROMPT = """You are an expert Meta Ads copywriter trained on Jim's Digital Marketing methodology.

Your task is to generate compelling headlines for Facebook/Instagram ads.

RULES YOU MUST FOLLOW:
1. [COPY-001] Headlines must be CONCISE (under 40 characters ideal, max 255)
2. Headlines must focus on the UNIQUE SELLING PROPOSITION (USP)
3. Use power words that grab attention
4. Create urgency or curiosity when appropriate
5. Avoid clickbait - be honest and direct

OUTPUT FORMAT:
Generate exactly 5 headlines, one per line, nothing else.
Each headline should be different in approach:
- Benefit-focused
- Urgency-based
- Question format
- Social proof angle
- Direct offer"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    def generate(
        self, 
        product_name: str,
        usp: str,
        usp_keywords: Optional[List[str]] = None,
        target_audience: Optional[str] = None,
        count: int = 5
    ) -> HeadlineResult:
        """
        Generate headline variations.
        
        Args:
            product_name: Name of the product/service
            usp: Unique Selling Proposition
            usp_keywords: Key USP words for validation
            target_audience: Description of target audience
            count: Number of headlines to generate
            
        Returns:
            HeadlineResult with headlines and validation
        """
        # Build the prompt
        user_prompt = f"""Generate {count} headlines for this product:

PRODUCT: {product_name}
USP: {usp}
TARGET AUDIENCE: {target_audience or 'Not specified'}

Remember: Headlines must be concise and focus on the USP."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.8,  # Higher creativity for copy
            max_tokens=300
        )
        
        # Parse headlines (one per line)
        raw_output = response.choices[0].message.content
        headlines = [
            line.strip().lstrip("1234567890.-) ") 
            for line in raw_output.strip().split("\n") 
            if line.strip() and not line.startswith("#")
        ][:count]
        
        # Extract USP keywords if not provided
        if not usp_keywords:
            usp_keywords = [w for w in usp.split() if len(w) > 4][:5]
        
        # Validate each headline
        validation = []
        for headline in headlines:
            val_result = validate_headline_has_usp(headline, usp_keywords)
            val_result["headline"] = headline
            val_result["length"] = len(headline)
            val_result["length_ok"] = len(headline) <= 40
            validation.append(val_result)
        
        return HeadlineResult(
            headlines=headlines,
            usp_keywords=usp_keywords,
            validation=validation,
            rule_citations=["COPY-001", "COPY-003"]
        )


# Singleton
_generator: Optional[HeadlineGenerator] = None


def get_headline_generator() -> HeadlineGenerator:
    global _generator
    if _generator is None:
        _generator = HeadlineGenerator()
    return _generator
