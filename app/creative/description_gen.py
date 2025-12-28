"""
Description Generator - Creative Studio.
Generates ad descriptions following Jim's strict <5 words rule.
"""
from typing import List, Optional
from openai import OpenAI
from pydantic import BaseModel
from app.config import settings
from app.knowledge_base.rules import validate_description_length


class DescriptionResult(BaseModel):
    """Result of description generation."""
    descriptions: List[str]
    validation: List[dict]
    rule_citations: List[str] = ["COPY-002", "COPY-003"]


class DescriptionGenerator:
    """
    Generates ad descriptions per Jim's methodology.
    
    Rules:
    - [COPY-002] Descriptions must be UNDER 5 WORDS
    - [COPY-003] Use different USP than headline
    """
    
    SYSTEM_PROMPT = """You are an expert Meta Ads copywriter.

Your task is to generate SHORT descriptions for Facebook/Instagram ads.

CRITICAL RULE [COPY-002]: Each description must be UNDER 5 WORDS.

Examples of good descriptions:
- "Free Shipping Today"
- "Shop Now"
- "Limited Time Offer"
- "Roasted Fresh Daily"
- "Save 20% Now"

OUTPUT FORMAT:
Generate exactly 5 descriptions, one per line.
Each must be UNDER 5 WORDS. No exceptions.
Do not number them or add any other text."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    def generate(
        self, 
        product_name: str,
        usp: str,
        headline_usp_used: Optional[str] = None,
        count: int = 5
    ) -> DescriptionResult:
        """
        Generate description variations.
        
        Args:
            product_name: Name of the product/service
            usp: Unique Selling Proposition  
            headline_usp_used: USP already used in headline (to avoid per COPY-003)
            count: Number of descriptions to generate
            
        Returns:
            DescriptionResult with descriptions and validation
        """
        # Build the prompt
        avoid_text = ""
        if headline_usp_used:
            avoid_text = f"\nAVOID using this USP (already in headline): {headline_usp_used}"
        
        user_prompt = f"""Generate {count} descriptions for:

PRODUCT: {product_name}
USP: {usp}{avoid_text}

REMEMBER: Each description must be UNDER 5 WORDS!"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=150
        )
        
        # Parse descriptions
        raw_output = response.choices[0].message.content
        descriptions = [
            line.strip().lstrip("1234567890.-) ").strip('"')
            for line in raw_output.strip().split("\n") 
            if line.strip() and not line.startswith("#")
        ][:count]
        
        # Validate each description
        validation = []
        for desc in descriptions:
            val_result = validate_description_length(desc)
            val_result["description"] = desc
            validation.append(val_result)
        
        # Filter to only valid descriptions
        valid_descriptions = [
            v["description"] for v in validation if v["valid"]
        ]
        
        # If we don't have enough valid ones, keep the shortest invalid ones
        if len(valid_descriptions) < count:
            invalid_sorted = sorted(
                [v for v in validation if not v["valid"]],
                key=lambda x: x["word_count"]
            )
            for v in invalid_sorted:
                if len(valid_descriptions) < count:
                    valid_descriptions.append(v["description"])
        
        return DescriptionResult(
            descriptions=valid_descriptions[:count],
            validation=validation,
            rule_citations=["COPY-002", "COPY-003"]
        )


# Singleton
_generator: Optional[DescriptionGenerator] = None


def get_description_generator() -> DescriptionGenerator:
    global _generator
    if _generator is None:
        _generator = DescriptionGenerator()
    return _generator
