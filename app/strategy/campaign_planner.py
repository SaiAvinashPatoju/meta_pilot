"""
Campaign Planner - The Architect.
Generates campaign structure based on Jim's methodology.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.models.campaign import CampaignRequirements, CampaignObjective


class AdSetConfig(BaseModel):
    """Configuration for a single Ad Set."""
    name: str
    audience_type: str  # "cold", "warm", "retargeting"
    targeting: Dict
    budget_percentage: float = 0.5  # Percentage of total budget
    optimization_goal: str = "CONVERSIONS"


class CampaignPlan(BaseModel):
    """Complete campaign plan ready for execution."""
    campaign_name: str
    objective: str
    special_ad_categories: List[str] = Field(default_factory=list)
    budget_optimization: str = "AD_SET_BUDGET"  # or "CAMPAIGN_BUDGET"
    daily_budget: float
    ad_sets: List[AdSetConfig]
    recommendations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    rule_citations: List[str] = Field(default_factory=list)


class CampaignPlanner:
    """
    Generates campaign structure based on requirements.
    Follows Jim's methodology for campaign architecture.
    """
    
    # Map our objectives to Meta API objectives
    OBJECTIVE_MAP = {
        CampaignObjective.SALES: "OUTCOME_SALES",
        CampaignObjective.LEADS: "OUTCOME_LEADS",
        CampaignObjective.TRAFFIC: "OUTCOME_TRAFFIC",
        CampaignObjective.ENGAGEMENT: "OUTCOME_ENGAGEMENT",
        CampaignObjective.APP_INSTALLS: "OUTCOME_APP_PROMOTION",
        CampaignObjective.AWARENESS: "OUTCOME_AWARENESS",
    }
    
    def generate_plan(self, requirements: CampaignRequirements) -> CampaignPlan:
        """
        Generate a complete campaign plan from requirements.
        
        Args:
            requirements: The 5 pillars of campaign requirements
            
        Returns:
            CampaignPlan with structure and recommendations
        """
        recommendations = []
        warnings = []
        rule_citations = []
        
        # Determine campaign objective
        objective = self.OBJECTIVE_MAP.get(
            requirements.objective, 
            "OUTCOME_SALES"
        )
        
        # Per [CAMP-001]: Use Sales for e-commerce
        if requirements.business_type and "commerce" in requirements.business_type.lower():
            objective = "OUTCOME_SALES"
            rule_citations.append("CAMP-001")
            recommendations.append("Using Sales objective for e-commerce per [CAMP-001]")
        
        # Generate campaign name
        product_slug = (requirements.product_name or "Campaign").replace(" ", "_")[:20]
        campaign_name = f"{product_slug}_{requirements.objective.value if requirements.objective else 'sales'}"
        
        # Determine budget strategy
        daily_budget = requirements.budget_amount or 20.0
        
        # Per [BUDGET-001]: Recommend $5-10/day per ad set for testing
        if daily_budget < 10:
            warnings.append("Budget below recommended $10/day minimum per [BUDGET-001]")
            rule_citations.append("BUDGET-001")
        
        # Per [BUDGET-002]: Use ABO for testing, CBO for scaling
        budget_optimization = "AD_SET_BUDGET"  # ABO for testing
        if daily_budget >= 50:
            budget_optimization = "CAMPAIGN_BUDGET"  # CBO for scaling
            recommendations.append("Using Campaign Budget Optimization (CBO) for scaling per [BUDGET-002]")
        else:
            recommendations.append("Using Ad Set Budget (ABO) for testing phase per [BUDGET-002]")
        rule_citations.append("BUDGET-002")
        
        # Generate Ad Sets based on requirements
        ad_sets = self._generate_ad_sets(requirements, daily_budget)
        
        # Check pixel status per [PIXEL-001]
        if not requirements.pixel_installed:
            warnings.append("⚠️ Facebook Pixel not installed - tracking will not work [PIXEL-001]")
            rule_citations.append("PIXEL-001")
        
        return CampaignPlan(
            campaign_name=campaign_name,
            objective=objective,
            budget_optimization=budget_optimization,
            daily_budget=daily_budget,
            ad_sets=ad_sets,
            recommendations=recommendations,
            warnings=warnings,
            rule_citations=list(set(rule_citations))
        )
    
    def _generate_ad_sets(
        self, 
        requirements: CampaignRequirements,
        total_budget: float
    ) -> List[AdSetConfig]:
        """Generate ad set configurations."""
        ad_sets = []
        targeting = requirements.targeting
        
        # Ad Set 1: Cold Audience (Prospecting)
        cold_targeting = {
            "geo_locations": {
                "countries": [],
                "cities": [],
                "regions": []
            },
            "age_min": targeting.age_min,
            "age_max": targeting.age_max,
        }
        
        # Parse locations
        for loc in targeting.locations:
            loc_upper = loc.upper().strip()
            # Check if it's a 2-letter state/country code
            if len(loc_upper) == 2:
                cold_targeting["geo_locations"]["regions"].append({"key": loc_upper})
            else:
                cold_targeting["geo_locations"]["cities"].append({"name": loc})
        
        # Add interests if specified
        if targeting.interests:
            cold_targeting["interests"] = [{"name": i} for i in targeting.interests]
        
        # Per [CAMP-003]: Use radius targeting for local businesses
        if targeting.radius_miles:
            cold_targeting["geo_locations"]["location_types"] = ["home", "recent"]
            # Note: Actual radius targeting requires lat/lng in real API
        
        ad_sets.append(AdSetConfig(
            name=f"Prospecting - {'Interest' if targeting.interests else 'Broad'}",
            audience_type="cold",
            targeting=cold_targeting,
            budget_percentage=0.7,  # 70% to cold
            optimization_goal="CONVERSIONS" if requirements.objective == CampaignObjective.SALES else "LINK_CLICKS"
        ))
        
        # Ad Set 2: Retargeting (Warm Audience)
        # Per [CAMP-002]: Create separate Ad Sets for Cold and Warm
        warm_targeting = {
            "custom_audiences": [
                {"name": "Website Visitors - 30 days"},
                {"name": "Video Viewers - 50%"},
                {"name": "Page Engagers - 30 days"}
            ],
            "age_min": targeting.age_min,
            "age_max": targeting.age_max,
        }
        
        ad_sets.append(AdSetConfig(
            name="Retargeting - Warm Audience",
            audience_type="retargeting",
            targeting=warm_targeting,
            budget_percentage=0.3,  # 30% to retargeting
            optimization_goal="CONVERSIONS"
        ))
        
        return ad_sets
    
    def get_budget_allocation(self, ad_sets: List[AdSetConfig], total_budget: float) -> Dict[str, float]:
        """Calculate budget for each ad set."""
        allocation = {}
        for ad_set in ad_sets:
            allocation[ad_set.name] = round(total_budget * ad_set.budget_percentage, 2)
        return allocation


# Singleton instance
_planner: Optional[CampaignPlanner] = None


def get_campaign_planner() -> CampaignPlanner:
    """Get or create campaign planner singleton."""
    global _planner
    if _planner is None:
        _planner = CampaignPlanner()
    return _planner
