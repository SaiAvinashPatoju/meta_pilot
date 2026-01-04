"""
Deterministic Rules Engine for MetaPilot.
Encodes Jim's methodology as hard logic - LLM explains decisions, rules MAKE decisions.

Key Rules:
- Learning Phase: days < 3 → NO structural changes
- CPL Threshold: CPL > 2x target AND spend > min_spend → PAUSE creative
- Budget Scaling: max +20% per adjustment
- Data Sufficiency: leads < 10 → insufficient data for decisions
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any


class DecisionType(str, Enum):
    """Types of decisions the rules engine can make."""
    NO_ACTION = "no_action"
    PAUSE_CREATIVE = "pause_creative"
    SCALE_BUDGET = "scale_budget"
    REDUCE_BUDGET = "reduce_budget"
    DUPLICATE_ADSET = "duplicate_adset"
    KILL_CAMPAIGN = "kill_campaign"
    WAIT_FOR_DATA = "wait_for_data"
    LEARNING_PHASE = "learning_phase"
    OPTIMIZE_CREATIVE = "optimize_creative"


class ConfidenceLevel(str, Enum):
    """Confidence level based on data sufficiency."""
    INSUFFICIENT = "insufficient"  # < 10 leads
    LOW = "low"                    # 10-25 leads
    MEDIUM = "medium"              # 25-50 leads
    HIGH = "high"                  # 50+ leads


@dataclass
class Decision:
    """A decision made by the rules engine."""
    decision_type: DecisionType
    confidence: ConfidenceLevel
    reasoning: str
    constraints: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    do_not: List[str] = field(default_factory=list)  # Explicit "what NOT to do"
    data_points: Dict[str, Any] = field(default_factory=dict)
    disclaimer: str = "Based on available data. Results may vary."
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision_type.value,
            "confidence": self.confidence.value,
            "reasoning": self.reasoning,
            "constraints": self.constraints,
            "recommendations": self.recommendations,
            "do_not": self.do_not,
            "data_points": self.data_points,
            "disclaimer": self.disclaimer,
        }


@dataclass
class CampaignMetrics:
    """Current campaign performance metrics."""
    campaign_id: str
    days_running: int
    total_spend: float
    total_leads: int
    impressions: int
    clicks: int
    cpl: float  # Cost per lead
    target_cpl: float
    ctr: float  # Click-through rate
    daily_budget: float
    creatives: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def cpl_ratio(self) -> float:
        """CPL as ratio of target (1.0 = on target, 2.0 = 2x target)."""
        if self.target_cpl <= 0:
            return 0.0
        return self.cpl / self.target_cpl if self.cpl > 0 else 0.0


class RulesEngine:
    """
    Deterministic rules engine for Meta Ads decisions.
    
    This engine makes decisions based on hard-coded rules from Jim's methodology.
    The LLM's job is to EXPLAIN these decisions, not override them.
    """
    
    # Configuration thresholds
    LEARNING_PHASE_DAYS = 3
    MIN_LEADS_FOR_DECISION = 10
    MIN_LEADS_LOW_CONFIDENCE = 25
    MIN_LEADS_MEDIUM_CONFIDENCE = 50
    MIN_SPEND_FOR_PAUSE = 100  # USD - minimum spend before pausing
    CPL_PAUSE_THRESHOLD = 2.0  # Pause if CPL > 2x target
    CPL_SCALE_THRESHOLD = 0.8  # Scale if CPL < 80% of target
    MAX_BUDGET_INCREASE = 0.20  # Max 20% budget increase
    MAX_BUDGET_DECREASE = 0.30  # Max 30% budget decrease
    MIN_CTR_THRESHOLD = 0.5  # Minimum acceptable CTR %
    
    def __init__(self, custom_thresholds: Optional[Dict[str, float]] = None):
        """Initialize with optional custom thresholds."""
        if custom_thresholds:
            for key, value in custom_thresholds.items():
                if hasattr(self, key.upper()):
                    setattr(self, key.upper(), value)
    
    def get_confidence_level(self, leads: int) -> ConfidenceLevel:
        """Determine confidence level based on data volume."""
        if leads < self.MIN_LEADS_FOR_DECISION:
            return ConfidenceLevel.INSUFFICIENT
        elif leads < self.MIN_LEADS_LOW_CONFIDENCE:
            return ConfidenceLevel.LOW
        elif leads < self.MIN_LEADS_MEDIUM_CONFIDENCE:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH
    
    def check_learning_phase(self, metrics: CampaignMetrics) -> Optional[Decision]:
        """
        Rule: If campaign is in learning phase (< 3 days), no structural changes.
        """
        if metrics.days_running < self.LEARNING_PHASE_DAYS:
            remaining_days = self.LEARNING_PHASE_DAYS - metrics.days_running
            return Decision(
                decision_type=DecisionType.LEARNING_PHASE,
                confidence=ConfidenceLevel.HIGH,  # This rule is absolute
                reasoning=f"Campaign is in learning phase (Day {metrics.days_running}/{self.LEARNING_PHASE_DAYS}). "
                          f"Facebook's algorithm needs time to optimize delivery.",
                constraints=[
                    f"Wait {remaining_days} more day(s) before making structural changes",
                    "Do not pause, duplicate, or significantly modify ad sets",
                    "Do not judge performance during this period",
                ],
                recommendations=[
                    "Monitor metrics but avoid knee-jerk reactions",
                    "Ensure pixel is firing correctly",
                    "Check that ads are approved and delivering",
                ],
                do_not=[
                    "Do NOT pause any ad sets",
                    "Do NOT change targeting",
                    "Do NOT adjust budgets by more than 10%",
                    "Do NOT make creative changes",
                    "Do NOT judge CPL during learning phase",
                ],
                data_points={
                    "days_running": metrics.days_running,
                    "learning_phase_duration": self.LEARNING_PHASE_DAYS,
                    "days_remaining": remaining_days,
                },
                disclaimer="Learning phase rule is absolute. Violating it resets the algorithm."
            )
        return None
    
    def check_data_sufficiency(self, metrics: CampaignMetrics) -> Optional[Decision]:
        """
        Rule: If leads < 10, insufficient data for decisions.
        """
        confidence = self.get_confidence_level(metrics.total_leads)
        
        if confidence == ConfidenceLevel.INSUFFICIENT:
            return Decision(
                decision_type=DecisionType.WAIT_FOR_DATA,
                confidence=ConfidenceLevel.INSUFFICIENT,
                reasoning=f"Only {metrics.total_leads} leads collected. Need minimum {self.MIN_LEADS_FOR_DECISION} "
                          f"leads to make statistically meaningful decisions.",
                constraints=[
                    f"Continue running until {self.MIN_LEADS_FOR_DECISION} leads are collected",
                    "Current CPL is not reliable for decision-making",
                ],
                recommendations=[
                    "Let the campaign run for more data",
                    f"Expected to reach {self.MIN_LEADS_FOR_DECISION} leads in "
                    f"{self._estimate_days_to_target(metrics, self.MIN_LEADS_FOR_DECISION)} days at current pace",
                ],
                do_not=[
                    "Do NOT make CPL-based decisions yet",
                    "Do NOT pause underperforming creatives",
                    "Do NOT scale budget based on current data",
                ],
                data_points={
                    "current_leads": metrics.total_leads,
                    "required_leads": self.MIN_LEADS_FOR_DECISION,
                    "current_cpl": metrics.cpl,
                    "note": "CPL unreliable with insufficient data",
                },
                disclaimer="Decisions made with insufficient data are unreliable."
            )
        return None
    
    def check_cpl_threshold(self, metrics: CampaignMetrics) -> Optional[Decision]:
        """
        Rule: If CPL > 2x target AND spend > minimum, pause creative.
        """
        if metrics.cpl_ratio >= self.CPL_PAUSE_THRESHOLD and metrics.total_spend >= self.MIN_SPEND_FOR_PAUSE:
            confidence = self.get_confidence_level(metrics.total_leads)
            return Decision(
                decision_type=DecisionType.PAUSE_CREATIVE,
                confidence=confidence,
                reasoning=f"CPL (₹{metrics.cpl:.0f}) is {metrics.cpl_ratio:.1f}x target (₹{metrics.target_cpl:.0f}). "
                          f"With ₹{metrics.total_spend:.0f} spent, this creative is not viable.",
                constraints=[
                    "Pause underperforming ad sets/creatives",
                    "Do not delete - keep for learning",
                    "Reallocate budget to better performers",
                ],
                recommendations=[
                    "Identify which specific creatives are driving high CPL",
                    "Test new angles/hooks before scaling",
                    "Review targeting - may be too broad",
                ],
                do_not=[
                    "Do NOT continue spending on this creative",
                    "Do NOT increase budget",
                    "Do NOT duplicate underperforming ad sets",
                ],
                data_points={
                    "current_cpl": metrics.cpl,
                    "target_cpl": metrics.target_cpl,
                    "cpl_ratio": metrics.cpl_ratio,
                    "total_spend": metrics.total_spend,
                    "threshold": f"{self.CPL_PAUSE_THRESHOLD}x target",
                },
                disclaimer="Based on current performance data. Market conditions may change."
            )
        return None
    
    def check_scaling_opportunity(self, metrics: CampaignMetrics) -> Optional[Decision]:
        """
        Rule: If CPL < 80% target AND sufficient data, can scale (max +20%).
        """
        confidence = self.get_confidence_level(metrics.total_leads)
        
        if (metrics.cpl_ratio <= self.CPL_SCALE_THRESHOLD and 
            confidence in [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH]):
            
            max_new_budget = metrics.daily_budget * (1 + self.MAX_BUDGET_INCREASE)
            recommended_increase = metrics.daily_budget * self.MAX_BUDGET_INCREASE
            
            return Decision(
                decision_type=DecisionType.SCALE_BUDGET,
                confidence=confidence,
                reasoning=f"CPL (₹{metrics.cpl:.0f}) is {metrics.cpl_ratio:.0%} of target - excellent performance! "
                          f"With {metrics.total_leads} leads, confidence is {confidence.value}.",
                constraints=[
                    f"Maximum budget increase: {self.MAX_BUDGET_INCREASE:.0%} (₹{recommended_increase:.0f})",
                    f"New budget should not exceed ₹{max_new_budget:.0f}/day",
                    "Scale gradually - avoid shocking the algorithm",
                ],
                recommendations=[
                    f"Increase daily budget from ₹{metrics.daily_budget:.0f} to ₹{max_new_budget:.0f}",
                    "Monitor CPL for 24-48 hours after scaling",
                    "If CPL rises significantly, pause and reassess",
                    "Consider duplicating winning ad set instead of scaling",
                ],
                do_not=[
                    f"Do NOT increase budget by more than {self.MAX_BUDGET_INCREASE:.0%}",
                    "Do NOT scale multiple ad sets simultaneously",
                    "Do NOT change creative while scaling",
                ],
                data_points={
                    "current_cpl": metrics.cpl,
                    "target_cpl": metrics.target_cpl,
                    "cpl_ratio": metrics.cpl_ratio,
                    "current_budget": metrics.daily_budget,
                    "max_new_budget": max_new_budget,
                    "leads": metrics.total_leads,
                },
                disclaimer="Scaling may temporarily increase CPL. Monitor closely."
            )
        return None
    
    def check_ctr_health(self, metrics: CampaignMetrics) -> Optional[Decision]:
        """
        Rule: If CTR < 0.5%, creative needs attention.
        """
        if metrics.ctr < self.MIN_CTR_THRESHOLD and metrics.impressions > 1000:
            confidence = self.get_confidence_level(metrics.total_leads)
            return Decision(
                decision_type=DecisionType.OPTIMIZE_CREATIVE,
                confidence=confidence,
                reasoning=f"CTR ({metrics.ctr:.2f}%) is below minimum threshold ({self.MIN_CTR_THRESHOLD}%). "
                          f"Creative is not resonating with audience.",
                constraints=[
                    "Focus on creative improvement, not targeting",
                    "Test new hooks/headlines first",
                ],
                recommendations=[
                    "Review ad creative - is the hook compelling?",
                    "Test different first 3 seconds of video",
                    "Try different headline angles",
                    "Check if offer is clear and compelling",
                ],
                do_not=[
                    "Do NOT blame targeting for low CTR",
                    "Do NOT scale budget with poor CTR",
                    "Do NOT make multiple changes at once",
                ],
                data_points={
                    "current_ctr": metrics.ctr,
                    "min_ctr": self.MIN_CTR_THRESHOLD,
                    "impressions": metrics.impressions,
                    "clicks": metrics.clicks,
                },
                disclaimer="CTR benchmarks vary by industry. Compare to your historical data."
            )
        return None
    
    def evaluate(self, metrics: CampaignMetrics) -> Decision:
        """
        Main evaluation method. Returns the highest-priority decision.
        
        Priority order:
        1. Learning phase (absolute)
        2. Data sufficiency
        3. CPL threshold (pause)
        4. CTR health
        5. Scaling opportunity
        6. No action needed
        """
        # Priority 1: Learning phase
        decision = self.check_learning_phase(metrics)
        if decision:
            return decision
        
        # Priority 2: Data sufficiency
        decision = self.check_data_sufficiency(metrics)
        if decision:
            return decision
        
        # Priority 3: CPL threshold (pause bad performers)
        decision = self.check_cpl_threshold(metrics)
        if decision:
            return decision
        
        # Priority 4: CTR health
        decision = self.check_ctr_health(metrics)
        if decision:
            return decision
        
        # Priority 5: Scaling opportunity
        decision = self.check_scaling_opportunity(metrics)
        if decision:
            return decision
        
        # Default: No action needed
        confidence = self.get_confidence_level(metrics.total_leads)
        return Decision(
            decision_type=DecisionType.NO_ACTION,
            confidence=confidence,
            reasoning=f"Campaign is performing within acceptable parameters. "
                      f"CPL (₹{metrics.cpl:.0f}) is {metrics.cpl_ratio:.0%} of target.",
            constraints=["Continue monitoring daily"],
            recommendations=[
                "Review performance again in 24 hours",
                "Document what's working for future campaigns",
            ],
            do_not=[
                "Do NOT make changes for the sake of change",
                "Do NOT fix what isn't broken",
            ],
            data_points={
                "cpl": metrics.cpl,
                "target_cpl": metrics.target_cpl,
                "cpl_ratio": metrics.cpl_ratio,
                "leads": metrics.total_leads,
                "spend": metrics.total_spend,
                "days_running": metrics.days_running,
            },
            disclaimer="Performance is acceptable. Continue monitoring."
        )
    
    def _estimate_days_to_target(self, metrics: CampaignMetrics, target_leads: int) -> int:
        """Estimate days to reach target leads at current pace."""
        if metrics.days_running <= 0 or metrics.total_leads <= 0:
            return 7  # Default estimate
        
        leads_per_day = metrics.total_leads / metrics.days_running
        remaining_leads = target_leads - metrics.total_leads
        
        if leads_per_day <= 0:
            return 7
        
        return max(1, int(remaining_leads / leads_per_day))
    
    def validate_budget_change(
        self, 
        current_budget: float, 
        proposed_budget: float, 
        direction: str = "increase"
    ) -> Dict[str, Any]:
        """
        Validate a proposed budget change against rules.
        
        Returns dict with 'allowed', 'max_allowed', 'reasoning'.
        """
        if direction == "increase":
            max_allowed = current_budget * (1 + self.MAX_BUDGET_INCREASE)
            allowed = proposed_budget <= max_allowed
            return {
                "allowed": allowed,
                "proposed": proposed_budget,
                "max_allowed": max_allowed,
                "current": current_budget,
                "max_change_percent": f"{self.MAX_BUDGET_INCREASE:.0%}",
                "reasoning": f"Budget increase {'within' if allowed else 'exceeds'} "
                            f"{self.MAX_BUDGET_INCREASE:.0%} limit",
            }
        else:  # decrease
            max_decrease = current_budget * self.MAX_BUDGET_DECREASE
            min_allowed = current_budget - max_decrease
            allowed = proposed_budget >= min_allowed
            return {
                "allowed": allowed,
                "proposed": proposed_budget,
                "min_allowed": min_allowed,
                "current": current_budget,
                "max_change_percent": f"{self.MAX_BUDGET_DECREASE:.0%}",
                "reasoning": f"Budget decrease {'within' if allowed else 'exceeds'} "
                            f"{self.MAX_BUDGET_DECREASE:.0%} limit",
            }


# Singleton instance
_rules_engine: Optional[RulesEngine] = None


def get_rules_engine(custom_thresholds: Optional[Dict[str, float]] = None) -> RulesEngine:
    """Get or create the rules engine singleton."""
    global _rules_engine
    if _rules_engine is None:
        _rules_engine = RulesEngine(custom_thresholds)
    return _rules_engine
