"""
Campaign Executor - Orchestrates campaign publishing to Meta.
Connects the Strategy Engine output to Meta Marketing API.

NOTE: This is a scaffold - requires valid credentials to function.
"""
from typing import Dict, Optional
from pydantic import BaseModel, Field
from app.meta.client import (
    get_meta_client, 
    CampaignConfig, 
    AdSetConfig as MetaAdSetConfig,
    AdCreativeConfig,
    AdConfig,
    MetaAPIError
)
from app.strategy.campaign_planner import CampaignPlan, AdSetConfig
from app.models.campaign import CampaignRequirements


class ExecutionResult(BaseModel):
    """Result of campaign execution."""
    success: bool
    campaign_id: Optional[str] = None
    adset_ids: list = Field(default_factory=list)
    ad_ids: list = Field(default_factory=list)
    errors: list = Field(default_factory=list)
    status: str = "not_started"
    preview_url: Optional[str] = None


class CampaignExecutor:
    """
    Executes a campaign plan by creating entities in Meta.
    
    Workflow:
    1. Validate credentials
    2. Create Campaign
    3. Create Ad Sets
    4. Create Ad Creatives
    5. Create Ads
    6. Return preview/review links
    """
    
    def __init__(self):
        self.client = get_meta_client()
    
    def validate_credentials(self) -> bool:
        """Check if Meta credentials are configured and valid."""
        from app.meta.auth import get_auth_client
        
        auth = get_auth_client()
        if not auth.access_token:
            return False
        
        try:
            token_info = auth.debug_token()
            return token_info.is_valid
        except Exception:
            return False
    
    def execute_plan(
        self, 
        plan: CampaignPlan,
        headlines: list,
        descriptions: list,
        primary_text: str,
        page_id: str,
        link_url: str,
        image_hash: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a campaign plan in Meta.
        
        Args:
            plan: Generated campaign plan
            headlines: List of headline variations
            descriptions: List of description variations
            primary_text: Primary text (body copy)
            page_id: Facebook Page ID to publish from
            link_url: Destination URL for ads
            image_hash: Hash of uploaded image
            
        Returns:
            ExecutionResult with created entity IDs
        """
        result = ExecutionResult(success=False, status="starting")
        
        try:
            # Step 1: Create Campaign
            result.status = "creating_campaign"
            campaign_config = CampaignConfig(
                name=plan.campaign_name,
                objective=plan.objective,
                status="PAUSED",  # Always start paused for review
                special_ad_categories=plan.special_ad_categories,
                daily_budget=int(plan.daily_budget * 100) if plan.budget_optimization == "CAMPAIGN_BUDGET" else None
            )
            
            campaign_response = self.client.create_campaign(campaign_config)
            result.campaign_id = campaign_response.get("id")
            
            if not result.campaign_id:
                result.errors.append("Failed to create campaign")
                return result
            
            # Step 2: Create Ad Sets
            result.status = "creating_adsets"
            for adset in plan.ad_sets:
                adset_budget = int(plan.daily_budget * adset.budget_percentage * 100)
                
                meta_adset = MetaAdSetConfig(
                    name=adset.name,
                    campaign_id=result.campaign_id,
                    daily_budget=adset_budget,
                    optimization_goal=adset.optimization_goal,
                    billing_event="IMPRESSIONS",
                    bid_strategy="LOWEST_COST_WITHOUT_CAP",
                    targeting=adset.targeting,
                    status="PAUSED"
                )
                
                adset_response = self.client.create_adset(meta_adset)
                adset_id = adset_response.get("id")
                
                if adset_id:
                    result.adset_ids.append(adset_id)
                    
                    # Step 3: Create Ad Creative for each ad set
                    result.status = "creating_creatives"
                    creative_config = AdCreativeConfig(
                        name=f"{adset.name} - Creative",
                        object_story_spec={
                            "page_id": page_id,
                            "link_data": {
                                "link": link_url,
                                "message": primary_text,
                                "name": headlines[0] if headlines else plan.campaign_name,
                                "description": descriptions[0] if descriptions else "",
                                "call_to_action": {
                                    "type": "LEARN_MORE",
                                    "value": {"link": link_url}
                                }
                            }
                        }
                    )
                    
                    if image_hash:
                        creative_config.object_story_spec["link_data"]["image_hash"] = image_hash
                    
                    creative_response = self.client.create_ad_creative(creative_config)
                    creative_id = creative_response.get("id")
                    
                    if creative_id:
                        # Step 4: Create Ad
                        result.status = "creating_ads"
                        ad_config = AdConfig(
                            name=f"{adset.name} - Ad 1",
                            adset_id=adset_id,
                            creative_id=creative_id,
                            status="PAUSED"
                        )
                        
                        ad_response = self.client.create_ad(ad_config)
                        ad_id = ad_response.get("id")
                        
                        if ad_id:
                            result.ad_ids.append(ad_id)
            
            result.success = len(result.ad_ids) > 0
            result.status = "completed"
            
            # Generate Ads Manager preview URL
            if result.campaign_id:
                result.preview_url = f"https://business.facebook.com/adsmanager/manage/campaigns?act={self.client.ad_account_id}&selected_campaign_ids={result.campaign_id}"
            
        except MetaAPIError as e:
            result.errors.append(f"Meta API Error: {e.message} (code: {e.error_code})")
            result.status = "failed"
        except Exception as e:
            result.errors.append(f"Execution Error: {str(e)}")
            result.status = "failed"
        
        return result
    
    def get_execution_preview(self, plan: CampaignPlan) -> Dict:
        """
        Generate a preview of what would be created without actually creating it.
        Useful for user review before execution.
        """
        preview = {
            "campaign": {
                "name": plan.campaign_name,
                "objective": plan.objective,
                "budget": f"${plan.daily_budget}/day",
                "budget_optimization": plan.budget_optimization
            },
            "ad_sets": [],
            "warnings": plan.warnings,
            "recommendations": plan.recommendations,
            "rule_citations": plan.rule_citations
        }
        
        for adset in plan.ad_sets:
            preview["ad_sets"].append({
                "name": adset.name,
                "audience_type": adset.audience_type,
                "budget_allocation": f"{adset.budget_percentage * 100:.0f}%",
                "optimization_goal": adset.optimization_goal
            })
        
        return preview


# Singleton
_executor: Optional[CampaignExecutor] = None


def get_executor() -> CampaignExecutor:
    global _executor
    if _executor is None:
        _executor = CampaignExecutor()
    return _executor
