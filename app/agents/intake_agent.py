"""
Intake Agent for MetaPilot.
Validates inputs, detects missing data, forces clarification, normalizes values.

Uses Gemini Flash for fast, accurate input processing.
"""
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from app.engine.model_router import ModelRouter, TaskType, get_model_router
from app.engine.state_store import CampaignState


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    extracted_data: Dict[str, Any]
    missing_fields: List[str]
    clarification_needed: List[str]
    normalized_values: Dict[str, Any]
    confidence: float  # 0-1 confidence in extraction
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "extracted_data": self.extracted_data,
            "missing_fields": self.missing_fields,
            "clarification_needed": self.clarification_needed,
            "normalized_values": self.normalized_values,
            "confidence": self.confidence,
        }


class IntakeAgent:
    """
    Agent responsible for intake and validation of user inputs.
    
    Responsibilities:
    - Validate inputs against expected formats
    - Detect missing required data
    - Force clarification for vague answers
    - Normalize budgets, objectives, geography
    - Extract structured data from natural language
    """
    
    # Indian Tier-1 cities
    TIER1_CITIES = [
        "mumbai", "delhi", "new delhi", "bangalore", "bengaluru", 
        "hyderabad", "chennai", "kolkata"
    ]
    
    # Indian Tier-2 cities
    TIER2_CITIES = [
        "pune", "ahmedabad", "jaipur", "lucknow", "kanpur", "nagpur",
        "indore", "thane", "bhopal", "visakhapatnam", "vadodara",
        "surat", "coimbatore", "kochi", "patna", "gurgaon", "noida",
        "chandigarh", "ludhiana", "agra", "nashik", "rajkot"
    ]
    
    # Valid objectives
    VALID_OBJECTIVES = {
        "sales": ["sales", "purchase", "sell", "buy", "e-commerce", "ecommerce", "shopify", "revenue"],
        "leads": ["lead", "leads", "contact", "form", "signup", "sign up", "register", "enquiry"],
        "traffic": ["traffic", "visit", "click", "website", "landing page"],
        "engagement": ["engagement", "like", "comment", "share", "interaction"],
        "awareness": ["awareness", "brand", "reach", "visibility", "impression"],
        "app_installs": ["app", "install", "download", "mobile app"],
    }
    
    # Interest keywords for Indian digital marketing audience
    INTEREST_KEYWORDS = [
        "digital marketing", "small business", "e-commerce", "ecommerce",
        "instagram business", "facebook ads", "online shopping", "shopify",
        "dropshipping", "marketing", "entrepreneurship", "business owner",
        "social media marketing", "online business", "startup", "freelancer"
    ]
    
    # Behavior keywords
    BEHAVIOR_KEYWORDS = [
        "engaged shoppers", "page admins", "facebook page admins",
        "online buyers", "mobile shoppers", "admins of facebook pages",
        "small business owners", "frequent travelers"
    ]
    
    # Exclusion keywords
    EXCLUSION_KEYWORDS = [
        "job seekers", "job seeker", "students", "student", "unemployed",
        "competitors", "existing customers"
    ]
    
    EXTRACTION_PROMPT = """You are an input extraction agent. Extract structured information from the user's message.

Extract the following fields if present (return null if not found):
- objective: Campaign goal (sales/leads/traffic/engagement/awareness/app_installs)
- budget_amount: Numeric budget value
- budget_type: "daily" or "lifetime"
- budget_currency: "INR" or "USD"
- locations: List of locations/cities
- age_min: Minimum age (number)
- age_max: Maximum age (number)
- interests: List of interests
- behaviors: List of behaviors
- exclusions: List of audiences to exclude
- product_name: Name of product/service
- usp: Unique selling proposition
- pixel_installed: true/false/null

Return as JSON only, no explanation.

User message: {message}"""

    CLARIFICATION_PROMPT = """Based on the user's message, identify if any information is vague and needs clarification.

Vague indicators:
- "everyone" or "all people" for targeting (too broad)
- No specific budget number
- Generic product description without USP
- Location like "everywhere" or "nationwide" without specifics

User message: {message}
Current collected data: {collected}

If clarification is needed, return a JSON with:
- needs_clarification: true/false
- fields: list of field names needing clarification
- questions: list of specific questions to ask

Return JSON only."""

    def __init__(self, model_router: Optional[ModelRouter] = None):
        """Initialize the intake agent."""
        self.router = model_router or get_model_router()
    
    def validate_and_extract(
        self, 
        message: str, 
        current_state: Optional[CampaignState] = None
    ) -> ValidationResult:
        """
        Validate user input and extract structured data.
        
        Args:
            message: User's natural language input
            current_state: Current campaign state for context
            
        Returns:
            ValidationResult with extracted data and validation status
        """
        extracted = {}
        missing = []
        clarification = []
        normalized = {}
        confidence = 0.0
        
        message_lower = message.lower()
        
        # 1. Extract objective
        objective = self._extract_objective(message_lower)
        if objective:
            extracted["objective"] = objective
            normalized["objective"] = objective
            confidence += 0.2
        elif not current_state or not current_state.objective:
            missing.append("objective")
        
        # 2. Extract budget
        budget_info = self._extract_budget(message)
        if budget_info["amount"]:
            extracted["budget_amount"] = budget_info["amount"]
            extracted["budget_type"] = budget_info["type"]
            normalized["daily_budget"] = self._normalize_budget(
                budget_info["amount"], 
                budget_info["type"],
                budget_info["currency"]
            )
            confidence += 0.2
        elif not current_state or current_state.daily_budget <= 0:
            missing.append("budget")
        
        # 3. Extract locations
        locations = self._extract_locations(message_lower)
        if locations:
            extracted["locations"] = locations
            normalized["locations"] = locations
            confidence += 0.2
        elif not current_state or not current_state.locations:
            missing.append("targeting")
        
        # 4. Extract age range
        age_range = self._extract_age_range(message)
        if age_range:
            extracted["age_min"] = age_range[0]
            extracted["age_max"] = age_range[1]
            normalized["age_min"] = age_range[0]
            normalized["age_max"] = age_range[1]
        
        # 5. Extract interests
        interests = self._extract_interests(message_lower)
        if interests:
            extracted["interests"] = interests
            normalized["interests"] = interests
        
        # 6. Extract behaviors
        behaviors = self._extract_behaviors(message_lower)
        if behaviors:
            extracted["behaviors"] = behaviors
            normalized["behaviors"] = behaviors
        
        # 7. Extract exclusions
        exclusions = self._extract_exclusions(message_lower)
        if exclusions:
            extracted["exclusions"] = exclusions
            normalized["exclusions"] = exclusions
        
        # 8. Extract product name
        product = self._extract_product_name(message)
        if product:
            extracted["product_name"] = product
            normalized["product_name"] = product
            confidence += 0.2
        elif not current_state or not current_state.product_name:
            missing.append("product_name")
        
        # 9. Extract USP
        usp = self._extract_usp(message)
        if usp:
            extracted["usp"] = usp
            normalized["usp"] = usp
            confidence += 0.2
        elif not current_state or not current_state.usp:
            missing.append("usp")
        
        # 10. Check for vague answers needing clarification
        clarification = self._check_vague_answers(message_lower, extracted)
        
        # 11. Extract pixel status
        pixel = self._extract_pixel_status(message_lower)
        if pixel is not None:
            extracted["pixel_installed"] = pixel
            normalized["pixel_installed"] = pixel
        
        is_valid = len(missing) == 0 and len(clarification) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            extracted_data=extracted,
            missing_fields=missing,
            clarification_needed=clarification,
            normalized_values=normalized,
            confidence=min(confidence, 1.0),
        )
    
    def _extract_objective(self, message: str) -> Optional[str]:
        """Extract campaign objective from message."""
        for objective, keywords in self.VALID_OBJECTIVES.items():
            if any(kw in message for kw in keywords):
                return objective
        return None
    
    def _extract_budget(self, message: str) -> Dict[str, Any]:
        """Extract budget information from message."""
        result = {"amount": None, "type": "daily", "currency": "INR"}
        
        # Look for INR amounts (₹ or Rs or rupees)
        inr_match = re.search(r'[₹₨]?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:rs|rupees?|inr)?', message, re.IGNORECASE)
        if inr_match:
            amount_str = inr_match.group(1).replace(",", "")
            result["amount"] = float(amount_str)
            result["currency"] = "INR"
        
        # Look for USD amounts
        usd_match = re.search(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', message)
        if usd_match:
            amount_str = usd_match.group(1).replace(",", "")
            result["amount"] = float(amount_str)
            result["currency"] = "USD"
        
        # Check for lifetime vs daily
        if "lifetime" in message.lower():
            result["type"] = "lifetime"
        elif "daily" in message.lower() or "per day" in message.lower() or "/day" in message.lower():
            result["type"] = "daily"
        
        return result
    
    def _extract_locations(self, message: str) -> List[str]:
        """Extract locations from message."""
        locations = []
        
        # Check for tier patterns
        if "tier-1" in message or "tier 1" in message or "tier1" in message:
            locations.extend([c.title() for c in self.TIER1_CITIES])
        if "tier-2" in message or "tier 2" in message or "tier2" in message:
            locations.extend([c.title() for c in self.TIER2_CITIES])
        
        # Check for individual cities
        for city in self.TIER1_CITIES + self.TIER2_CITIES:
            if city in message:
                locations.append(city.title())
        
        # Check for "india" as country-level
        if "india" in message and not locations:
            locations.append("India")
        
        # Check for pan-india
        if "pan-india" in message or "pan india" in message:
            locations = ["India"]
        
        return list(set(locations))
    
    def _extract_age_range(self, message: str) -> Optional[Tuple[int, int]]:
        """Extract age range from message."""
        # Pattern: 22-38, 22 to 38, 22–38
        age_match = re.search(r'(\d{2})\s*[-–to]+\s*(\d{2})', message)
        if age_match:
            age_min, age_max = int(age_match.group(1)), int(age_match.group(2))
            if 13 <= age_min <= 65 and 13 <= age_max <= 65:
                return (age_min, age_max)
        return None
    
    def _extract_interests(self, message: str) -> List[str]:
        """Extract interests from message."""
        found = [kw for kw in self.INTEREST_KEYWORDS if kw in message]
        return list(set(found))
    
    def _extract_behaviors(self, message: str) -> List[str]:
        """Extract behaviors from message."""
        found = [kw for kw in self.BEHAVIOR_KEYWORDS if kw in message]
        return list(set(found))
    
    def _extract_exclusions(self, message: str) -> List[str]:
        """Extract exclusions from message."""
        if "exclude" not in message and "exclusion" not in message and "not target" not in message:
            return []
        found = [kw for kw in self.EXCLUSION_KEYWORDS if kw in message]
        return list(set(found))
    
    def _extract_product_name(self, message: str) -> Optional[str]:
        """Extract product name from message."""
        # Look for quoted text
        quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', message)
        if quoted:
            return quoted[0][0] or quoted[0][1]
        
        # Look for "called X" or "named X" patterns
        name_match = re.search(
            r'(?:called|named|selling|product is|service is|promoting)\s+([A-Za-z0-9\s]+?)(?:\.|,|$|\s+for|\s+to|\s+in)',
            message, 
            re.IGNORECASE
        )
        if name_match:
            name = name_match.group(1).strip()
            if len(name) > 2 and len(name) < 50:
                return name
        
        return None
    
    def _extract_usp(self, message: str) -> Optional[str]:
        """Extract USP from message."""
        usp_patterns = [
            r'(?:unique|special|different|best|usp)\s*(?:is|:)?\s*(.+?)(?:\.|$)',
            r'(?:we|our)\s+(?:offer|provide|have)\s+(.+?)(?:\.|$)',
            r'(?:what makes us different|our advantage)\s*(?:is|:)?\s*(.+?)(?:\.|$)',
        ]
        
        for pattern in usp_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                usp = match.group(1).strip()
                if len(usp) > 10 and len(usp) < 200:
                    return usp
        
        return None
    
    def _extract_pixel_status(self, message: str) -> Optional[bool]:
        """Extract pixel installation status from message."""
        if "pixel" not in message:
            return None
        
        if any(word in message for word in ["yes", "installed", "ready", "set up", "have"]):
            return True
        elif any(word in message for word in ["no", "not", "don't", "haven't"]):
            return False
        
        return None
    
    def _check_vague_answers(self, message: str, extracted: Dict[str, Any]) -> List[str]:
        """Check for vague answers that need clarification."""
        clarification = []
        
        # Check for vague targeting
        vague_targeting = ["everyone", "all people", "anybody", "all ages", "all genders"]
        if any(vt in message for vt in vague_targeting):
            clarification.append("targeting_too_broad")
        
        # Check for vague location
        vague_locations = ["everywhere", "worldwide", "global", "all over"]
        if any(vl in message for vl in vague_locations):
            clarification.append("location_too_broad")
        
        # Check for missing budget specifics
        if "budget" in message and not extracted.get("budget_amount"):
            clarification.append("budget_not_specific")
        
        return clarification
    
    def _normalize_budget(
        self, 
        amount: float, 
        budget_type: str, 
        currency: str
    ) -> float:
        """Normalize budget to daily INR amount."""
        # Convert USD to INR (approximate rate)
        if currency == "USD":
            amount = amount * 83  # Approximate exchange rate
        
        # Convert lifetime to daily (assume 30-day campaign)
        if budget_type == "lifetime":
            amount = amount / 30
        
        return amount
    
    def generate_clarification_question(
        self, 
        field: str, 
        current_state: Optional[CampaignState] = None
    ) -> str:
        """Generate a clarification question for a missing or vague field."""
        questions = {
            "objective": "What's the main goal for this campaign? Are you looking to drive sales, generate leads, or build brand awareness?",
            "budget": "What's your daily budget for this campaign? Jim recommends starting with ₹500-1000/day for testing.",
            "targeting": "Which cities do you want to target? For India, I'd suggest focusing on Tier-1 cities (Mumbai, Delhi, Bangalore) or Tier-2 cities (Pune, Jaipur, Kochi).",
            "targeting_too_broad": "Targeting 'everyone' usually leads to wasted spend. Who specifically buys your product? What age range? What are their interests?",
            "location_too_broad": "Targeting everywhere is too broad. Let's narrow it down - which specific cities or regions are your customers in?",
            "budget_not_specific": "Could you give me a specific budget number? For example, ₹500/day or ₹15,000 lifetime?",
            "product_name": "What's the name of the product or service you're advertising?",
            "usp": "What makes your product unique? What's the #1 reason customers should choose you over competitors?",
        }
        
        return questions.get(field, f"Could you provide more details about your {field}?")


# Singleton instance
_intake_agent: Optional[IntakeAgent] = None


def get_intake_agent() -> IntakeAgent:
    """Get or create the intake agent singleton."""
    global _intake_agent
    if _intake_agent is None:
        _intake_agent = IntakeAgent()
    return _intake_agent
