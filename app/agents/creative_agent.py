"""
Creative Agent for MetaPilot.
Generates ad copy, headlines, and descriptions.

This agent is ISOLATED from performance data - it only handles creative generation.
Uses higher-quality model for creative output.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.engine.model_router import ModelRouter, TaskType, get_model_router
from app.engine.state_store import CampaignState


@dataclass
class CreativeOutput:
    """Generated creative output."""
    headlines: List[str]
    primary_texts: List[str]
    descriptions: List[str]
    cta_options: List[str]
    hooks: List[str]
    rationale: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "headlines": self.headlines,
            "primary_texts": self.primary_texts,
            "descriptions": self.descriptions,
            "cta_options": self.cta_options,
            "hooks": self.hooks,
            "rationale": self.rationale,
        }


class CreativeAgent:
    """
    Agent responsible for generating ad creative copy.
    
    Key isolation:
    - NO access to performance data (CPL, spend, etc.)
    - Only receives product info, USP, and targeting
    - Focuses purely on creative quality
    """
    
    HEADLINE_PROMPT = """You are an expert Meta Ads copywriter creating headlines for the Indian market.

Product: {product_name}
USP: {usp}
Target Audience: {audience_description}
Objective: {objective}

RULES (from Jim's methodology):
1. Headlines must be concise (under 40 characters ideal)
2. Lead with the USP or main benefit
3. Use power words that create urgency or curiosity
4. Avoid clickbait - be honest and direct
5. Consider Indian context (₹, local references if relevant)

Generate exactly 5 headlines:
- 1 USP-focused headline
- 1 benefit-focused headline  
- 1 curiosity-driven headline
- 1 urgency/scarcity headline
- 1 social proof headline (if applicable)

Format: Return ONLY the 5 headlines, one per line, no numbering or explanation."""

    PRIMARY_TEXT_PROMPT = """You are an expert Meta Ads copywriter creating primary text for the Indian market.

Product: {product_name}
USP: {usp}
Target Audience: {audience_description}
Objective: {objective}
Key Benefits: {benefits}

RULES:
1. Hook in the first line - stop the scroll
2. Address the pain point or desire
3. Present the solution (the product)
4. Include social proof if possible
5. End with a clear CTA
6. Keep under 125 characters for best results (or 2-3 short paragraphs max)
7. Use emojis sparingly but effectively

Generate exactly 3 primary text variations:
- 1 short-form (2-3 lines)
- 1 medium-form (4-5 lines)
- 1 story-based (problem → solution format)

Separate each variation with ---"""

    DESCRIPTION_PROMPT = """You are an expert Meta Ads copywriter creating descriptions.

Product: {product_name}
USP: {usp}

RULES (CRITICAL):
1. Descriptions must be UNDER 5 WORDS
2. Support the headline, don't repeat it
3. Add urgency or credibility
4. Be extremely concise

Generate exactly 5 descriptions (under 5 words each):"""

    HOOKS_PROMPT = """You are creating scroll-stopping hooks for video ads in the Indian market.

Product: {product_name}
USP: {usp}
Target Audience: {audience_description}
Pain Points: {pain_points}

Create 5 video hooks (first 3 seconds of a video ad):
- Each hook should stop someone from scrolling
- Use curiosity, shock, or direct address
- Keep under 10 words
- Consider what would make the target audience pause

Format: One hook per line, no numbering."""

    CTA_OPTIONS = [
        "Shop Now",
        "Learn More", 
        "Sign Up",
        "Get Started",
        "Book Now",
        "Get Offer",
        "Contact Us",
        "Download",
        "Subscribe",
        "Get Quote",
    ]

    def __init__(self, model_router: Optional[ModelRouter] = None):
        """Initialize the creative agent."""
        self.router = model_router or get_model_router()
    
    def generate_creative(
        self, 
        state: CampaignState,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> CreativeOutput:
        """
        Generate complete ad creative based on campaign state.
        
        Args:
            state: Campaign state with product info and targeting
            additional_context: Optional extra context (pain points, benefits, etc.)
            
        Returns:
            CreativeOutput with headlines, primary texts, descriptions, etc.
        """
        context = additional_context or {}
        
        # Build audience description
        audience_desc = self._build_audience_description(state)
        
        # Generate headlines
        headlines = self._generate_headlines(state, audience_desc)
        
        # Generate primary texts
        primary_texts = self._generate_primary_texts(state, audience_desc, context)
        
        # Generate descriptions
        descriptions = self._generate_descriptions(state)
        
        # Generate hooks
        hooks = self._generate_hooks(state, audience_desc, context)
        
        # Select appropriate CTAs
        ctas = self._select_ctas(state.objective)
        
        # Generate rationale
        rationale = self._generate_rationale(state)
        
        return CreativeOutput(
            headlines=headlines,
            primary_texts=primary_texts,
            descriptions=descriptions,
            cta_options=ctas,
            hooks=hooks,
            rationale=rationale,
        )
    
    def _build_audience_description(self, state: CampaignState) -> str:
        """Build a natural language description of the target audience."""
        parts = []
        
        if state.age_min and state.age_max:
            parts.append(f"Age {state.age_min}-{state.age_max}")
        
        if state.locations:
            parts.append(f"in {', '.join(state.locations[:3])}")
        
        if state.interests:
            parts.append(f"interested in {', '.join(state.interests[:3])}")
        
        if state.behaviors:
            parts.append(f"who are {', '.join(state.behaviors[:2])}")
        
        return " ".join(parts) if parts else "broad audience in India"
    
    def _generate_headlines(self, state: CampaignState, audience_desc: str) -> List[str]:
        """Generate headline variations."""
        prompt = self.HEADLINE_PROMPT.format(
            product_name=state.product_name or "the product",
            usp=state.usp or "quality and value",
            audience_description=audience_desc,
            objective=state.objective or "conversions",
        )
        
        try:
            response = self.router.generate(
                task_type=TaskType.COPYWRITING,
                prompt=prompt,
            )
            
            # Parse response into list
            headlines = [h.strip() for h in response.strip().split("\n") if h.strip()]
            return headlines[:5] if headlines else self._fallback_headlines(state)
            
        except Exception:
            return self._fallback_headlines(state)
    
    def _generate_primary_texts(
        self, 
        state: CampaignState, 
        audience_desc: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate primary text variations."""
        prompt = self.PRIMARY_TEXT_PROMPT.format(
            product_name=state.product_name or "the product",
            usp=state.usp or "quality and value",
            audience_description=audience_desc,
            objective=state.objective or "conversions",
            benefits=context.get("benefits", "great value, quality results"),
        )
        
        try:
            response = self.router.generate(
                task_type=TaskType.COPYWRITING,
                prompt=prompt,
            )
            
            # Parse response - split by ---
            texts = [t.strip() for t in response.split("---") if t.strip()]
            return texts[:3] if texts else self._fallback_primary_texts(state)
            
        except Exception:
            return self._fallback_primary_texts(state)
    
    def _generate_descriptions(self, state: CampaignState) -> List[str]:
        """Generate short descriptions (under 5 words each)."""
        prompt = self.DESCRIPTION_PROMPT.format(
            product_name=state.product_name or "the product",
            usp=state.usp or "quality",
        )
        
        try:
            response = self.router.generate(
                task_type=TaskType.COPYWRITING,
                prompt=prompt,
            )
            
            descriptions = [d.strip() for d in response.strip().split("\n") if d.strip()]
            # Filter to only short descriptions
            descriptions = [d for d in descriptions if len(d.split()) <= 6]
            return descriptions[:5] if descriptions else self._fallback_descriptions()
            
        except Exception:
            return self._fallback_descriptions()
    
    def _generate_hooks(
        self, 
        state: CampaignState, 
        audience_desc: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """Generate video ad hooks."""
        prompt = self.HOOKS_PROMPT.format(
            product_name=state.product_name or "the product",
            usp=state.usp or "amazing value",
            audience_description=audience_desc,
            pain_points=context.get("pain_points", "common frustrations"),
        )
        
        try:
            response = self.router.generate(
                task_type=TaskType.COPYWRITING,
                prompt=prompt,
            )
            
            hooks = [h.strip() for h in response.strip().split("\n") if h.strip()]
            return hooks[:5] if hooks else self._fallback_hooks()
            
        except Exception:
            return self._fallback_hooks()
    
    def _select_ctas(self, objective: Optional[str]) -> List[str]:
        """Select appropriate CTAs based on objective."""
        objective_ctas = {
            "sales": ["Shop Now", "Get Offer", "Buy Now"],
            "leads": ["Sign Up", "Get Quote", "Contact Us"],
            "traffic": ["Learn More", "Read More", "Visit Site"],
            "engagement": ["Learn More", "See More", "Watch Now"],
            "awareness": ["Learn More", "See More"],
            "app_installs": ["Download", "Install Now", "Get App"],
        }
        
        return objective_ctas.get(objective, ["Learn More", "Shop Now", "Get Started"])
    
    def _generate_rationale(self, state: CampaignState) -> str:
        """Generate rationale for creative choices."""
        parts = []
        
        if state.usp:
            parts.append(f"Headlines focus on your USP: '{state.usp}'")
        
        if state.objective:
            parts.append(f"Copy optimized for {state.objective} objective")
        
        if state.locations:
            parts.append(f"Tailored for {', '.join(state.locations[:2])} audience")
        
        parts.append("Following Jim's methodology: concise headlines, under-5-word descriptions")
        
        return ". ".join(parts) + "."
    
    # Fallback methods for when LLM fails
    def _fallback_headlines(self, state: CampaignState) -> List[str]:
        product = state.product_name or "This"
        return [
            f"Discover {product} Today",
            f"Transform Your Results with {product}",
            f"Why Everyone's Talking About {product}",
            f"Limited Time: {product} Offer",
            f"Join 1000+ Happy Customers",
        ]
    
    def _fallback_primary_texts(self, state: CampaignState) -> List[str]:
        product = state.product_name or "our solution"
        return [
            f"Ready to transform your results? {product} delivers real value. Try it today! 🚀",
            f"Struggling to get results? You're not alone.\n\n{product} has helped thousands achieve their goals.\n\nJoin them today →",
            f"Here's what changed everything for me...\n\nI discovered {product} and never looked back.\n\nThe results speak for themselves. 📈",
        ]
    
    def _fallback_descriptions(self) -> List[str]:
        return [
            "Limited time offer",
            "Free shipping available",
            "Trusted by thousands",
            "Results guaranteed",
            "Start today",
        ]
    
    def _fallback_hooks(self) -> List[str]:
        return [
            "Stop scrolling - this changes everything",
            "Wait, you need to see this",
            "Nobody's talking about this hack",
            "I wish I knew this sooner",
            "This is exactly what you need",
        ]
    
    def regenerate_headlines(
        self, 
        state: CampaignState, 
        feedback: str
    ) -> List[str]:
        """Regenerate headlines with specific feedback."""
        audience_desc = self._build_audience_description(state)
        
        prompt = f"""{self.HEADLINE_PROMPT.format(
            product_name=state.product_name or "the product",
            usp=state.usp or "quality and value",
            audience_description=audience_desc,
            objective=state.objective or "conversions",
        )}

ADDITIONAL FEEDBACK: {feedback}
Incorporate this feedback while following all the rules above."""
        
        try:
            response = self.router.generate(
                task_type=TaskType.COPYWRITING,
                prompt=prompt,
            )
            headlines = [h.strip() for h in response.strip().split("\n") if h.strip()]
            return headlines[:5]
        except Exception:
            return self._fallback_headlines(state)


# Singleton instance
_creative_agent: Optional[CreativeAgent] = None


def get_creative_agent() -> CreativeAgent:
    """Get or create the creative agent singleton."""
    global _creative_agent
    if _creative_agent is None:
        _creative_agent = CreativeAgent()
    return _creative_agent
