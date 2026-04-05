"""
Meta Marketing API Client.
Handles OAuth2 authentication and API calls to Meta's Marketing API.

NOTE: This is a scaffold - requires valid credentials to function.
"""
import requests
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from app.config import settings


class MetaAPIError(Exception):
    """Exception raised for Meta API errors."""
    def __init__(self, message: str, error_code: Optional[int] = None, error_subcode: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        self.error_subcode = error_subcode
        super().__init__(self.message)


class AccessTokenInfo(BaseModel):
    """Information about a Meta access token."""
    access_token: str
    token_type: str = "bearer"
    expires_in: Optional[int] = None
    is_valid: bool = False
    scopes: List[str] = Field(default_factory=list)
    app_id: Optional[str] = None
    user_id: Optional[str] = None


class MetaAuthClient:
    """
    Handles OAuth2 authentication with Meta.
    
    OAuth Flow:
    1. User visits authorization URL
    2. User grants permissions
    3. Meta redirects to callback with code
    4. Exchange code for access token
    5. Use token for API calls
    """
    
    AUTH_URL = "https://www.facebook.com/v18.0/dialog/oauth"
    TOKEN_URL = "https://graph.facebook.com/v18.0/oauth/access_token"
    DEBUG_TOKEN_URL = "https://graph.facebook.com/debug_token"
    
    def __init__(self):
        self.app_id = settings.meta_app_id
        self.app_secret = settings.meta_app_secret
        self.redirect_uri = settings.meta_redirect_uri
        self._access_token: Optional[str] = settings.meta_access_token
    
    @property
    def access_token(self) -> Optional[str]:
        return self._access_token
    
    @access_token.setter
    def access_token(self, token: str):
        self._access_token = token
    
    def get_authorization_url(self, state: str = None) -> str:
        """
        Generate the OAuth authorization URL.
        
        Required scopes for Ads:
        - ads_management
        - ads_read
        - business_management
        """
        scopes = [
            "ads_management",
            "ads_read",
            "business_management",
            "pages_read_engagement"
        ]
        
        params = {
            "client_id": self.app_id,
            "redirect_uri": self.redirect_uri,
            "scope": ",".join(scopes),
            "response_type": "code",
        }
        
        if state:
            params["state"] = state
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.AUTH_URL}?{query}"
    
    def exchange_code_for_token(self, code: str) -> AccessTokenInfo:
        """Exchange authorization code for access token."""
        params = {
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "redirect_uri": self.redirect_uri,
            "code": code
        }
        
        response = requests.get(self.TOKEN_URL, params=params, timeout=10)
        data = response.json()
        
        if "error" in data:
            raise MetaAPIError(
                message=data.get("error", {}).get("message", "Token exchange failed"),
                error_code=data.get("error", {}).get("code")
            )
        
        self._access_token = data.get("access_token")
        
        return AccessTokenInfo(
            access_token=data.get("access_token"),
            token_type=data.get("token_type", "bearer"),
            expires_in=data.get("expires_in"),
            is_valid=True
        )
    
    def debug_token(self, token: str = None) -> AccessTokenInfo:
        """Check if an access token is valid and get its info."""
        token_to_check = token or self._access_token
        
        if not token_to_check:
            return AccessTokenInfo(access_token="", is_valid=False)
        
        params = {
            "input_token": token_to_check,
            "access_token": f"{self.app_id}|{self.app_secret}"
        }
        
        response = requests.get(self.DEBUG_TOKEN_URL, params=params, timeout=10)
        data = response.json().get("data", {})
        
        return AccessTokenInfo(
            access_token=token_to_check,
            is_valid=data.get("is_valid", False),
            scopes=data.get("scopes", []),
            app_id=data.get("app_id"),
            user_id=data.get("user_id"),
            expires_in=data.get("expires_at")
        )
    
    def get_long_lived_token(self, short_lived_token: str) -> AccessTokenInfo:
        """Exchange a short-lived token for a long-lived one."""
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.app_id,
            "client_secret": self.app_secret,
            "fb_exchange_token": short_lived_token
        }
        
        response = requests.get(self.TOKEN_URL, params=params, timeout=10)
        data = response.json()
        
        if "error" in data:
            raise MetaAPIError(
                message=data.get("error", {}).get("message", "Token exchange failed"),
                error_code=data.get("error", {}).get("code")
            )
        
        self._access_token = data.get("access_token")
        
        return AccessTokenInfo(
            access_token=data.get("access_token"),
            token_type="bearer",
            expires_in=data.get("expires_in"),  # ~60 days for long-lived
            is_valid=True
        )


# Singleton
_auth_client: Optional[MetaAuthClient] = None


def get_auth_client() -> MetaAuthClient:
    global _auth_client
    if _auth_client is None:
        _auth_client = MetaAuthClient()
    return _auth_client
