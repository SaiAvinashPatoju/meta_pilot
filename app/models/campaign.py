"""
Pydantic models for campaign requirements and conversation state.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


class CampaignObjective(str, Enum):
    """Meta Ads campaign objectives."""
    SALES = "sales"
    LEADS = "leads"
    TRAFFIC = "traffic"
    ENGAGEMENT = "engagement"
    APP_INSTALLS = "app_installs"
    AWARENESS = "awareness"


class BudgetType(str, Enum):
    """Budget allocation type."""
    DAILY = "daily"
    LIFETIME = "lifetime"


class TargetingInfo(BaseModel):
    """Targeting configuration."""
    locations: List[str] = Field(default_factory=list, description="Target locations")
    age_min: int = Field(default=18, ge=13, le=65)
    age_max: int = Field(default=65, ge=13, le=65)
    genders: List[str] = Field(default_factory=lambda: ["all"])
    interests: List[str] = Field(default_factory=list)
    behaviors: List[str] = Field(default_factory=list, description="Behavioral targeting (e.g., Engaged shoppers)")
    exclusions: List[str] = Field(default_factory=list, description="Audiences to exclude (e.g., Job seekers)")
    custom_audiences: List[str] = Field(default_factory=list, description="Custom/lookalike audience IDs")
    radius_miles: Optional[int] = Field(default=None, description="Radius for local targeting")


class CampaignRequirements(BaseModel):
    """
    The 5 Pillars of campaign requirements.
    Agent must gather all of these before proceeding.
    """
    # Pillar 1: Objective
    objective: Optional[CampaignObjective] = Field(
        default=None,
        description="Campaign objective (Sales, Leads, Traffic, etc.)"
    )
    
    # Pillar 2: Budget
    budget_amount: Optional[float] = Field(
        default=None,
        ge=1.0,
        description="Budget amount in USD"
    )
    budget_type: BudgetType = Field(
        default=BudgetType.DAILY,
        description="Daily or Lifetime budget"
    )
    
    # Pillar 3: Targeting
    targeting: TargetingInfo = Field(
        default_factory=TargetingInfo,
        description="Audience targeting configuration"
    )
    
    # Pillar 4: USP (Unique Selling Proposition)
    usp: Optional[str] = Field(
        default=None,
        description="What makes the product/service unique"
    )
    usp_keywords: List[str] = Field(
        default_factory=list,
        description="Key USP words for headline validation"
    )
    
    # Pillar 5: Creative Assets
    product_name: Optional[str] = Field(
        default=None,
        description="Name of the product or service"
    )
    creative_urls: List[str] = Field(
        default_factory=list,
        description="URLs to creative assets (images/videos)"
    )
    
    # Additional context
    business_type: Optional[str] = Field(
        default=None,
        description="Type of business (e-commerce, local, service, etc.)"
    )
    pixel_installed: bool = Field(
        default=False,
        description="Whether Facebook Pixel is set up"
    )
    
    def missing_pillars(self) -> List[str]:
        """Return list of missing required pillars."""
        missing = []
        if not self.objective:
            missing.append("objective")
        if not self.budget_amount:
            missing.append("budget")
        if not self.targeting.locations:
            missing.append("targeting")
        if not self.usp:
            missing.append("usp")
        if not self.product_name:
            missing.append("product_name")
        return missing
    
    def is_complete(self) -> bool:
        """Check if all 5 pillars are gathered."""
        return len(self.missing_pillars()) == 0
    
    def completion_percentage(self) -> int:
        """Return percentage of pillars completed."""
        total = 5
        completed = total - len(self.missing_pillars())
        return int((completed / total) * 100)


class ConversationState(BaseModel):
    """State of the campaign building conversation."""
    session_id: str
    requirements: CampaignRequirements = Field(default_factory=CampaignRequirements)
    current_pillar: Optional[str] = Field(default=None, description="Currently gathering this pillar")
    messages: List[dict] = Field(default_factory=list)
    phase: Literal["gathering", "review", "generating", "complete"] = "gathering"
    
    def add_message(self, role: str, content: str):
        """Add a message to the conversation."""
        self.messages.append({"role": role, "content": content})
    
    def get_next_pillar(self) -> Optional[str]:
        """Get the next pillar to gather."""
        missing = self.requirements.missing_pillars()
        return missing[0] if missing else None
