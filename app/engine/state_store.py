"""
Campaign State Store for MetaPilot.
Persistent state layer - replaces chat-history-as-memory pattern.

Stores:
- Campaign requirements (5 pillars)
- Target metrics (CPL, budget)
- Creative performance history
- Decision log with timestamps
- Budget adjustment history
"""
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
import hashlib


@dataclass
class CreativeState:
    """State of an individual creative/ad."""
    creative_id: str
    name: str
    status: str = "active"  # active, paused, winner, loser
    spend: float = 0.0
    leads: int = 0
    impressions: int = 0
    clicks: int = 0
    cpl: float = 0.0
    ctr: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    paused_at: Optional[str] = None
    pause_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CreativeState":
        return cls(**data)


@dataclass
class DecisionLogEntry:
    """A logged decision made by the rules engine."""
    timestamp: str
    decision_type: str
    confidence: str
    reasoning: str
    metrics_snapshot: Dict[str, Any]
    action_taken: bool = False
    action_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionLogEntry":
        return cls(**data)


@dataclass
class BudgetHistoryEntry:
    """A budget change record."""
    timestamp: str
    old_budget: float
    new_budget: float
    change_percent: float
    reason: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BudgetHistoryEntry":
        return cls(**data)


@dataclass
class CampaignState:
    """
    Complete state of a campaign - persisted across sessions.
    This replaces relying on conversation history for state.
    """
    # Identity
    campaign_id: str
    session_id: str
    user_id: Optional[str] = None
    
    # 5 Pillars (from requirements gathering)
    objective: Optional[str] = None
    product_name: Optional[str] = None
    usp: Optional[str] = None
    
    # Targeting
    locations: List[str] = field(default_factory=list)
    age_min: int = 18
    age_max: int = 65
    interests: List[str] = field(default_factory=list)
    behaviors: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)
    
    # Budget
    daily_budget: float = 0.0
    lifetime_budget: Optional[float] = None
    budget_type: str = "daily"
    
    # Performance Targets
    target_cpl: float = 0.0
    target_roas: Optional[float] = None
    
    # Current Metrics (updated from Meta API)
    current_spend: float = 0.0
    current_leads: int = 0
    current_cpl: float = 0.0
    current_ctr: float = 0.0
    impressions: int = 0
    clicks: int = 0
    days_running: int = 0
    
    # Creative Management
    creatives: List[CreativeState] = field(default_factory=list)
    winning_creative_id: Optional[str] = None
    
    # Decision History
    decision_log: List[DecisionLogEntry] = field(default_factory=list)
    last_decision_timestamp: Optional[str] = None
    
    # Budget History
    budget_history: List[BudgetHistoryEntry] = field(default_factory=list)
    
    # Meta
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    phase: str = "gathering"  # gathering, active, optimizing, scaling, paused, complete
    pixel_installed: bool = False
    
    def add_creative(self, creative: CreativeState) -> None:
        """Add a creative to the campaign."""
        self.creatives.append(creative)
        self.updated_at = datetime.now().isoformat()
    
    def update_creative(self, creative_id: str, updates: Dict[str, Any]) -> bool:
        """Update a creative's state."""
        for creative in self.creatives:
            if creative.creative_id == creative_id:
                for key, value in updates.items():
                    if hasattr(creative, key):
                        setattr(creative, key, value)
                self.updated_at = datetime.now().isoformat()
                return True
        return False
    
    def pause_creative(self, creative_id: str, reason: str) -> bool:
        """Pause a creative with reason."""
        return self.update_creative(creative_id, {
            "status": "paused",
            "paused_at": datetime.now().isoformat(),
            "pause_reason": reason,
        })
    
    def set_winner(self, creative_id: str) -> bool:
        """Mark a creative as the winner."""
        for creative in self.creatives:
            if creative.creative_id == creative_id:
                creative.status = "winner"
                self.winning_creative_id = creative_id
                self.updated_at = datetime.now().isoformat()
                return True
        return False
    
    def log_decision(
        self, 
        decision_type: str, 
        confidence: str, 
        reasoning: str,
        metrics_snapshot: Dict[str, Any],
        action_taken: bool = False,
        action_notes: Optional[str] = None
    ) -> None:
        """Log a decision made by the rules engine."""
        entry = DecisionLogEntry(
            timestamp=datetime.now().isoformat(),
            decision_type=decision_type,
            confidence=confidence,
            reasoning=reasoning,
            metrics_snapshot=metrics_snapshot,
            action_taken=action_taken,
            action_notes=action_notes,
        )
        self.decision_log.append(entry)
        self.last_decision_timestamp = entry.timestamp
        self.updated_at = datetime.now().isoformat()
    
    def log_budget_change(
        self, 
        old_budget: float, 
        new_budget: float, 
        reason: str
    ) -> None:
        """Log a budget change."""
        change_percent = ((new_budget - old_budget) / old_budget * 100) if old_budget > 0 else 0
        entry = BudgetHistoryEntry(
            timestamp=datetime.now().isoformat(),
            old_budget=old_budget,
            new_budget=new_budget,
            change_percent=change_percent,
            reason=reason,
        )
        self.budget_history.append(entry)
        self.daily_budget = new_budget
        self.updated_at = datetime.now().isoformat()
    
    def get_active_creatives(self) -> List[CreativeState]:
        """Get all active creatives."""
        return [c for c in self.creatives if c.status == "active"]
    
    def get_paused_creatives(self) -> List[CreativeState]:
        """Get all paused creatives."""
        return [c for c in self.creatives if c.status == "paused"]
    
    def completion_percentage(self) -> int:
        """Calculate pillar completion percentage."""
        pillars = [
            self.objective is not None,
            self.daily_budget > 0 or self.lifetime_budget is not None,
            len(self.locations) > 0,
            self.usp is not None,
            self.product_name is not None,
        ]
        return int(sum(pillars) / len(pillars) * 100)
    
    def missing_pillars(self) -> List[str]:
        """Return list of missing pillars."""
        missing = []
        if not self.objective:
            missing.append("objective")
        if self.daily_budget <= 0 and self.lifetime_budget is None:
            missing.append("budget")
        if not self.locations:
            missing.append("targeting")
        if not self.usp:
            missing.append("usp")
        if not self.product_name:
            missing.append("product_name")
        return missing
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = asdict(self)
        # Convert nested dataclasses
        data["creatives"] = [c.to_dict() if isinstance(c, CreativeState) else c for c in self.creatives]
        data["decision_log"] = [d.to_dict() if isinstance(d, DecisionLogEntry) else d for d in self.decision_log]
        data["budget_history"] = [b.to_dict() if isinstance(b, BudgetHistoryEntry) else b for b in self.budget_history]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CampaignState":
        """Deserialize from dictionary."""
        # Convert nested dicts back to dataclasses
        if "creatives" in data:
            data["creatives"] = [
                CreativeState.from_dict(c) if isinstance(c, dict) else c 
                for c in data["creatives"]
            ]
        if "decision_log" in data:
            data["decision_log"] = [
                DecisionLogEntry.from_dict(d) if isinstance(d, dict) else d 
                for d in data["decision_log"]
            ]
        if "budget_history" in data:
            data["budget_history"] = [
                BudgetHistoryEntry.from_dict(b) if isinstance(b, dict) else b 
                for b in data["budget_history"]
            ]
        return cls(**data)


class StateStore:
    """
    Persistent state store for campaign states.
    Uses file-based JSON storage with optional Redis backend.
    """
    
    def __init__(self, storage_dir: str = "data/state"):
        """Initialize the state store."""
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, CampaignState] = {}
    
    def _get_file_path(self, campaign_id: str) -> Path:
        """Get the file path for a campaign state."""
        # Hash long IDs for filesystem compatibility
        safe_id = hashlib.md5(campaign_id.encode()).hexdigest()[:16]
        return self.storage_dir / f"campaign_{safe_id}.json"
    
    def save(self, state: CampaignState) -> bool:
        """Save campaign state to disk."""
        try:
            state.updated_at = datetime.now().isoformat()
            file_path = self._get_file_path(state.campaign_id)
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(state.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Update cache
            self._cache[state.campaign_id] = state
            return True
        except Exception as e:
            print(f"Error saving state: {e}")
            return False
    
    def load(self, campaign_id: str) -> Optional[CampaignState]:
        """Load campaign state from disk."""
        # Check cache first
        if campaign_id in self._cache:
            return self._cache[campaign_id]
        
        try:
            file_path = self._get_file_path(campaign_id)
            if not file_path.exists():
                return None
            
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            state = CampaignState.from_dict(data)
            self._cache[campaign_id] = state
            return state
        except Exception as e:
            print(f"Error loading state: {e}")
            return None
    
    def create(self, session_id: str, user_id: Optional[str] = None) -> CampaignState:
        """Create a new campaign state."""
        campaign_id = f"campaign_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{session_id[:8]}"
        state = CampaignState(
            campaign_id=campaign_id,
            session_id=session_id,
            user_id=user_id,
        )
        self.save(state)
        return state
    
    def delete(self, campaign_id: str) -> bool:
        """Delete a campaign state."""
        try:
            file_path = self._get_file_path(campaign_id)
            if file_path.exists():
                file_path.unlink()
            if campaign_id in self._cache:
                del self._cache[campaign_id]
            return True
        except Exception as e:
            print(f"Error deleting state: {e}")
            return False
    
    def list_campaigns(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all campaigns, optionally filtered by user."""
        campaigns = []
        for file_path in self.storage_dir.glob("campaign_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                if user_id is None or data.get("user_id") == user_id:
                    campaigns.append({
                        "campaign_id": data.get("campaign_id"),
                        "product_name": data.get("product_name"),
                        "objective": data.get("objective"),
                        "phase": data.get("phase"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                    })
            except Exception:
                continue
        
        # Sort by updated_at descending
        campaigns.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return campaigns
    
    def get_by_session(self, session_id: str) -> Optional[CampaignState]:
        """Get campaign state by session ID."""
        for file_path in self.storage_dir.glob("campaign_*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("session_id") == session_id:
                    return CampaignState.from_dict(data)
            except Exception:
                continue
        return None


# Singleton instance
_state_store: Optional[StateStore] = None


def get_state_store(storage_dir: str = "data/state") -> StateStore:
    """Get or create the state store singleton."""
    global _state_store
    if _state_store is None:
        _state_store = StateStore(storage_dir)
    return _state_store
