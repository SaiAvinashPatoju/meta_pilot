"""
Playbook rules extracted from Jim's Digital Marketing course.
These are hard-coded constraints that the LLM must cite.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel


class PlaybookRule(BaseModel):
    """A single rule from the video course playbook."""
    id: str
    category: str
    rule: str
    timestamp: str
    source: str = "Jim's Digital Marketing - Learn Meta Ads Step-by-Step"


# Extracted rules from the video course
PLAYBOOK_RULES: List[PlaybookRule] = [
    # Copywriting Rules
    PlaybookRule(
        id="COPY-001",
        category="copywriting",
        rule="Headlines must be concise and focused on the Unique Selling Proposition (USP).",
        timestamp="07:58:00"
    ),
    PlaybookRule(
        id="COPY-002",
        category="copywriting",
        rule="Descriptions must be under 5 words.",
        timestamp="07:59:00"
    ),
    PlaybookRule(
        id="COPY-003",
        category="copywriting",
        rule="Use different USPs for Headline vs Description - do not repeat the same selling point.",
        timestamp="07:59:00"
    ),
    PlaybookRule(
        id="COPY-004",
        category="copywriting",
        rule="Primary text should follow Problem-Agitation-Solution (PAS) framework.",
        timestamp="08:00:00"
    ),
    
    # Campaign Structure Rules
    PlaybookRule(
        id="CAMP-001",
        category="campaign_structure",
        rule="Use Sales objective for e-commerce conversion campaigns.",
        timestamp="01:19:39"
    ),
    PlaybookRule(
        id="CAMP-002",
        category="campaign_structure",
        rule="Create separate Ad Sets for Cold (prospecting) and Warm (retargeting) audiences.",
        timestamp="01:25:00"
    ),
    PlaybookRule(
        id="CAMP-003",
        category="campaign_structure",
        rule="For local businesses, use radius targeting for efficient geographic reach.",
        timestamp="01:25:59"
    ),
    
    # Targeting Rules
    PlaybookRule(
        id="TARG-001",
        category="targeting",
        rule="Use precise interest targeting OR broad targeting with specific creatives - not both.",
        timestamp="02:30:00"
    ),
    PlaybookRule(
        id="TARG-002",
        category="targeting",
        rule="Retargeting audiences should include: Video viewers, Add to Cart, Page visitors.",
        timestamp="03:00:00"
    ),
    
    # Pixel & Tracking Rules
    PlaybookRule(
        id="PIXEL-001",
        category="pixel",
        rule="Facebook Pixel must be installed and verified before launching any campaign.",
        timestamp="00:45:00"
    ),
    PlaybookRule(
        id="PIXEL-002",
        category="pixel",
        rule="Set up Conversion API (CAPI) for server-side tracking redundancy.",
        timestamp="00:50:00"
    ),
    
    # Budget Rules
    PlaybookRule(
        id="BUDGET-001",
        category="budget",
        rule="Start with testing budget: $5-10/day per ad set for initial testing.",
        timestamp="04:00:00"
    ),
    PlaybookRule(
        id="BUDGET-002",
        category="budget",
        rule="Use Campaign Budget Optimization (CBO) for scaling, Ad Set Budget (ABO) for testing.",
        timestamp="04:15:00"
    ),
]


def get_rules_by_category(category: str) -> List[PlaybookRule]:
    """Get all rules in a specific category."""
    return [r for r in PLAYBOOK_RULES if r.category == category]


def get_rule_by_id(rule_id: str) -> Optional[PlaybookRule]:
    """Get a specific rule by ID."""
    for rule in PLAYBOOK_RULES:
        if rule.id == rule_id:
            return rule
    return None


def get_all_rules() -> List[PlaybookRule]:
    """Get all playbook rules."""
    return PLAYBOOK_RULES


def format_rules_for_prompt(rules: Optional[List[PlaybookRule]] = None) -> str:
    """Format rules for injection into LLM prompt."""
    if rules is None:
        rules = PLAYBOOK_RULES
    
    formatted = "## Playbook Rules (You MUST cite these by ID when applicable)\n\n"
    for rule in rules:
        formatted += f"- **[{rule.id}]** ({rule.category}): {rule.rule} [Timestamp: {rule.timestamp}]\n"
    
    return formatted


def validate_description_length(description: str) -> Dict:
    """Validate that description follows the <5 words rule (COPY-002)."""
    words = description.strip().split()
    is_valid = len(words) < 5
    return {
        "valid": is_valid,
        "word_count": len(words),
        "rule_id": "COPY-002",
        "message": f"Description has {len(words)} words. " + 
                   ("Valid!" if is_valid else "Must be under 5 words.")
    }


def validate_headline_has_usp(headline: str, usp_keywords: List[str]) -> Dict:
    """Validate that headline contains USP keywords (COPY-001)."""
    headline_lower = headline.lower()
    found_keywords = [kw for kw in usp_keywords if kw.lower() in headline_lower]
    is_valid = len(found_keywords) > 0
    return {
        "valid": is_valid,
        "found_keywords": found_keywords,
        "rule_id": "COPY-001",
        "message": f"Headline {'contains' if is_valid else 'missing'} USP keywords."
    }
