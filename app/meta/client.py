"""
Meta Marketing API Client for Campaign/AdSet/Ad management.

NOTE: This is a scaffold - requires valid credentials and approved app.
"""
import requests
from typing import Dict, Optional, List, Any
from pydantic import BaseModel, Field
from app.config import settings
from app.meta.auth import get_auth_client, MetaAPIError


class CampaignConfig(BaseModel):
    """Configuration for creating a Meta campaign."""
    name: str
    objective: str  # OUTCOME_SALES, OUTCOME_LEADS, etc.
    status: str = "PAUSED"  # ACTIVE, PAUSED
    special_ad_categories: List[str] = Field(default_factory=list)
    # CBO settings
    daily_budget: Optional[int] = None  # In cents
    lifetime_budget: Optional[int] = None  # In cents


class AdSetConfig(BaseModel):
    """Configuration for creating an Ad Set."""
    name: str
    campaign_id: str
    daily_budget: Optional[int] = None  # In cents
    lifetime_budget: Optional[int] = None
    optimization_goal: str = "CONVERSIONS"
    billing_event: str = "IMPRESSIONS"
    bid_strategy: str = "LOWEST_COST_WITHOUT_CAP"
    targeting: Dict[str, Any] = Field(default_factory=dict)
    status: str = "PAUSED"
    start_time: Optional[str] = None  # ISO format
    end_time: Optional[str] = None


class AdCreativeConfig(BaseModel):
    """Configuration for ad creative."""
    name: str
    object_story_spec: Dict[str, Any]
    # For link ads
    link_data: Optional[Dict[str, Any]] = None


class AdConfig(BaseModel):
    """Configuration for creating an Ad."""
    name: str
    adset_id: str
    creative_id: str
    status: str = "PAUSED"


class MetaAdsClient:
    """
    Client for Meta Marketing API.
    
    Handles:
    - Campaign CRUD
    - Ad Set CRUD
    - Ad Creative creation
    - Ad CRUD
    """
    
    API_VERSION = "v18.0"
    BASE_URL = f"https://graph.facebook.com/{API_VERSION}"
    
    def __init__(self):
        self.auth = get_auth_client()
        self.ad_account_id = settings.meta_ad_account_id
    
    @property
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.auth.access_token}"}
    
    def _account_url(self, endpoint: str) -> str:
        return f"{self.BASE_URL}/act_{self.ad_account_id}/{endpoint}"
    
    def _handle_response(self, response: requests.Response) -> Dict:
        """Handle API response and raise errors if needed."""
        data = response.json()
        
        if "error" in data:
            error = data["error"]
            raise MetaAPIError(
                message=error.get("message", "Unknown error"),
                error_code=error.get("code"),
                error_subcode=error.get("error_subcode")
            )
        
        return data
    
    # ============ Campaigns ============
    
    def create_campaign(self, config: CampaignConfig) -> Dict:
        """Create a new campaign."""
        payload = {
            "name": config.name,
            "objective": config.objective,
            "status": config.status,
            "special_ad_categories": config.special_ad_categories,
        }
        
        if config.daily_budget:
            payload["daily_budget"] = config.daily_budget
        if config.lifetime_budget:
            payload["lifetime_budget"] = config.lifetime_budget
        
        response = requests.post(
            self._account_url("campaigns"),
            headers=self._headers,
            json=payload,
            timeout=30
        )
        
        return self._handle_response(response)
    
    def get_campaigns(self, fields: List[str] = None) -> List[Dict]:
        """Get all campaigns for the ad account."""
        fields = fields or ["id", "name", "status", "objective", "created_time"]
        
        response = requests.get(
            self._account_url("campaigns"),
            headers=self._headers,
            params={"fields": ",".join(fields)},
            timeout=30
        )
        
        data = self._handle_response(response)
        return data.get("data", [])
    
    def update_campaign(self, campaign_id: str, updates: Dict) -> Dict:
        """Update a campaign."""
        response = requests.post(
            f"{self.BASE_URL}/{campaign_id}",
            headers=self._headers,
            json=updates,
            timeout=30
        )
        
        return self._handle_response(response)
    
    def delete_campaign(self, campaign_id: str) -> Dict:
        """Delete a campaign."""
        response = requests.delete(
            f"{self.BASE_URL}/{campaign_id}",
            headers=self._headers,
            timeout=30
        )
        
        return self._handle_response(response)
    
    # ============ Ad Sets ============
    
    def create_adset(self, config: AdSetConfig) -> Dict:
        """Create a new ad set."""
        payload = {
            "name": config.name,
            "campaign_id": config.campaign_id,
            "optimization_goal": config.optimization_goal,
            "billing_event": config.billing_event,
            "bid_strategy": config.bid_strategy,
            "targeting": config.targeting,
            "status": config.status,
        }
        
        if config.daily_budget:
            payload["daily_budget"] = config.daily_budget
        if config.lifetime_budget:
            payload["lifetime_budget"] = config.lifetime_budget
        if config.start_time:
            payload["start_time"] = config.start_time
        if config.end_time:
            payload["end_time"] = config.end_time
        
        response = requests.post(
            self._account_url("adsets"),
            headers=self._headers,
            json=payload,
            timeout=30
        )
        
        return self._handle_response(response)
    
    def get_adsets(self, campaign_id: str = None, fields: List[str] = None) -> List[Dict]:
        """Get ad sets, optionally filtered by campaign."""
        fields = fields or ["id", "name", "status", "daily_budget", "optimization_goal"]
        
        url = self._account_url("adsets")
        params = {"fields": ",".join(fields)}
        
        if campaign_id:
            params["filtering"] = f'[{{"field":"campaign_id","operator":"EQUAL","value":"{campaign_id}"}}]'
        
        response = requests.get(url, headers=self._headers, params=params, timeout=30)
        
        data = self._handle_response(response)
        return data.get("data", [])
    
    # ============ Ad Creatives ============
    
    def create_ad_creative(self, config: AdCreativeConfig) -> Dict:
        """Create an ad creative."""
        payload = {
            "name": config.name,
            "object_story_spec": config.object_story_spec,
        }
        
        response = requests.post(
            self._account_url("adcreatives"),
            headers=self._headers,
            json=payload,
            timeout=30
        )
        
        return self._handle_response(response)
    
    # ============ Ads ============
    
    def create_ad(self, config: AdConfig) -> Dict:
        """Create an ad."""
        payload = {
            "name": config.name,
            "adset_id": config.adset_id,
            "creative": {"creative_id": config.creative_id},
            "status": config.status,
        }
        
        response = requests.post(
            self._account_url("ads"),
            headers=self._headers,
            json=payload,
            timeout=30
        )
        
        return self._handle_response(response)
    
    def get_ads(self, adset_id: str = None, fields: List[str] = None) -> List[Dict]:
        """Get ads, optionally filtered by ad set."""
        fields = fields or ["id", "name", "status", "created_time"]
        
        url = self._account_url("ads")
        params = {"fields": ",".join(fields)}
        
        if adset_id:
            params["filtering"] = f'[{{"field":"adset_id","operator":"EQUAL","value":"{adset_id}"}}]'
        
        response = requests.get(url, headers=self._headers, params=params, timeout=30)
        
        data = self._handle_response(response)
        return data.get("data", [])
    
    def get_campaign_insights(
        self, 
        campaign_id: str,
        date_preset: str = "last_7d",
        fields: List[str] = None
    ) -> List[Dict]:
        """Get performance insights for a campaign."""
        fields = fields or [
            "impressions", "clicks", "spend", "cpc", "cpm",
            "reach", "frequency", "actions", "conversions"
        ]
        
        response = requests.get(
            f"{self.BASE_URL}/{campaign_id}/insights",
            headers=self._headers,
            params={
                "fields": ",".join(fields),
                "date_preset": date_preset
            },
            timeout=30
        )
        
        data = self._handle_response(response)
        return data.get("data", [])


# Singleton
_client: Optional[MetaAdsClient] = None


def get_meta_client() -> MetaAdsClient:
    global _client
    if _client is None:
        _client = MetaAdsClient()
    return _client
