"""
Analysis Agent for MetaPilot.
Reads metrics, applies deterministic rules, outputs decisions with confidence levels.

This agent:
- ONLY analyzes data, does not make creative decisions
- Uses rules engine for all decisions
- Provides confidence levels based on data sufficiency
- Generates human-readable analysis reports
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from app.engine.model_router import ModelRouter, TaskType, get_model_router
from app.engine.rules_engine import (
    RulesEngine, Decision, CampaignMetrics, 
    ConfidenceLevel, get_rules_engine
)
from app.engine.state_store import CampaignState, CreativeState


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance snapshot."""
    timestamp: str
    cpl: float
    target_cpl: float
    cpl_ratio: float
    spend: float
    leads: int
    impressions: int
    clicks: int
    ctr: float
    days_running: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpl": self.cpl,
            "target_cpl": self.target_cpl,
            "cpl_ratio": self.cpl_ratio,
            "spend": self.spend,
            "leads": self.leads,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "ctr": self.ctr,
            "days_running": self.days_running,
        }


@dataclass  
class CreativeAnalysis:
    """Analysis of individual creative performance."""
    creative_id: str
    name: str
    status: str
    spend: float
    leads: int
    cpl: float
    ctr: float
    verdict: str  # "winner", "underperformer", "testing", "insufficient_data"
    recommendation: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "name": self.name,
            "status": self.status,
            "spend": self.spend,
            "leads": self.leads,
            "cpl": self.cpl,
            "ctr": self.ctr,
            "verdict": self.verdict,
            "recommendation": self.recommendation,
        }


@dataclass
class AnalysisReport:
    """Complete analysis report."""
    campaign_id: str
    generated_at: str
    overall_health: str  # "healthy", "warning", "critical", "learning"
    confidence_level: ConfidenceLevel
    performance_snapshot: PerformanceSnapshot
    creative_analyses: List[CreativeAnalysis]
    primary_decision: Decision
    summary: str
    key_insights: List[str]
    data_quality_notes: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "generated_at": self.generated_at,
            "overall_health": self.overall_health,
            "confidence_level": self.confidence_level.value,
            "performance_snapshot": self.performance_snapshot.to_dict(),
            "creative_analyses": [c.to_dict() for c in self.creative_analyses],
            "primary_decision": self.primary_decision.to_dict(),
            "summary": self.summary,
            "key_insights": self.key_insights,
            "data_quality_notes": self.data_quality_notes,
        }


class AnalysisAgent:
    """
    Agent responsible for campaign performance analysis.
    
    Key principles:
    - Data-driven decisions only
    - Clear confidence levels
    - Deterministic via rules engine
    - Human-readable outputs
    """
    
    SUMMARY_PROMPT = """You are a media buying analyst creating a performance summary.

Campaign Data:
- Days Running: {days_running}
- Total Spend: ₹{spend}
- Total Leads: {leads}
- CPL: ₹{cpl} (target: ₹{target_cpl})
- CPL vs Target: {cpl_ratio:.0%}
- CTR: {ctr:.2f}%
- Impressions: {impressions:,}

Decision from Rules Engine: {decision_type}
Confidence Level: {confidence}

Write a 2-3 sentence executive summary of campaign performance.
Be direct and include specific numbers.
Mention the confidence level naturally.
Do not be overly positive or negative - be factual."""

    INSIGHTS_PROMPT = """Based on this campaign data, identify 3-5 key insights.

Performance:
- CPL: ₹{cpl} vs target ₹{target_cpl} ({cpl_ratio:.0%} of target)
- CTR: {ctr:.2f}%
- Spend: ₹{spend}
- Leads: {leads}
- Days: {days_running}

Creative Performance:
{creative_summary}

Generate exactly 3-5 insights, each on its own line.
Each insight should be actionable and specific.
Include numbers where relevant.
Format: Start each insight with an emoji (✅, ⚠️, 📊, 💡, 🎯)"""

    def __init__(
        self, 
        model_router: Optional[ModelRouter] = None,
        rules_engine: Optional[RulesEngine] = None
    ):
        """Initialize the analysis agent."""
        self.router = model_router or get_model_router()
        self.rules = rules_engine or get_rules_engine()
    
    def analyze_campaign(
        self, 
        state: CampaignState,
        fresh_metrics: Optional[Dict[str, Any]] = None
    ) -> AnalysisReport:
        """
        Perform complete campaign analysis.
        
        Args:
            state: Campaign state with historical data
            fresh_metrics: Optional fresh metrics from Meta API
            
        Returns:
            AnalysisReport with all analysis results
        """
        # Update state with fresh metrics if provided
        if fresh_metrics:
            state.current_spend = fresh_metrics.get("spend", state.current_spend)
            state.current_leads = fresh_metrics.get("leads", state.current_leads)
            state.current_cpl = fresh_metrics.get("cpl", state.current_cpl)
            state.current_ctr = fresh_metrics.get("ctr", state.current_ctr)
            state.impressions = fresh_metrics.get("impressions", state.impressions)
            state.clicks = fresh_metrics.get("clicks", state.clicks)
            state.days_running = fresh_metrics.get("days_running", state.days_running)
        
        # Build metrics object
        metrics = self._build_metrics(state)
        
        # Create performance snapshot
        snapshot = self._create_snapshot(metrics)
        
        # Analyze creatives
        creative_analyses = self._analyze_creatives(state, metrics)
        
        # Get primary decision from rules engine
        decision = self.rules.evaluate(metrics)
        
        # Determine overall health
        health = self._determine_health(decision, metrics)
        
        # Get confidence level
        confidence = self.rules.get_confidence_level(metrics.total_leads)
        
        # Generate summary using LLM
        summary = self._generate_summary(metrics, decision)
        
        # Generate insights using LLM
        insights = self._generate_insights(metrics, creative_analyses)
        
        # Data quality notes
        data_notes = self._assess_data_quality(metrics, state)
        
        return AnalysisReport(
            campaign_id=state.campaign_id,
            generated_at=datetime.now().isoformat(),
            overall_health=health,
            confidence_level=confidence,
            performance_snapshot=snapshot,
            creative_analyses=creative_analyses,
            primary_decision=decision,
            summary=summary,
            key_insights=insights,
            data_quality_notes=data_notes,
        )
    
    def _build_metrics(self, state: CampaignState) -> CampaignMetrics:
        """Build CampaignMetrics from state."""
        return CampaignMetrics(
            campaign_id=state.campaign_id,
            days_running=state.days_running,
            total_spend=state.current_spend,
            total_leads=state.current_leads,
            impressions=state.impressions,
            clicks=state.clicks,
            cpl=state.current_cpl,
            target_cpl=state.target_cpl,
            ctr=state.current_ctr,
            daily_budget=state.daily_budget,
        )
    
    def _create_snapshot(self, metrics: CampaignMetrics) -> PerformanceSnapshot:
        """Create a performance snapshot."""
        return PerformanceSnapshot(
            timestamp=datetime.now().isoformat(),
            cpl=metrics.cpl,
            target_cpl=metrics.target_cpl,
            cpl_ratio=metrics.cpl_ratio,
            spend=metrics.total_spend,
            leads=metrics.total_leads,
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            ctr=metrics.ctr,
            days_running=metrics.days_running,
        )
    
    def _analyze_creatives(
        self, 
        state: CampaignState, 
        campaign_metrics: CampaignMetrics
    ) -> List[CreativeAnalysis]:
        """Analyze individual creative performance."""
        analyses = []
        
        for creative in state.creatives:
            verdict, recommendation = self._evaluate_creative(
                creative, 
                state.target_cpl,
                campaign_metrics.total_leads
            )
            
            analyses.append(CreativeAnalysis(
                creative_id=creative.creative_id,
                name=creative.name,
                status=creative.status,
                spend=creative.spend,
                leads=creative.leads,
                cpl=creative.cpl,
                ctr=creative.ctr,
                verdict=verdict,
                recommendation=recommendation,
            ))
        
        return analyses
    
    def _evaluate_creative(
        self, 
        creative: CreativeState, 
        target_cpl: float,
        total_campaign_leads: int
    ) -> tuple:
        """Evaluate a single creative and return verdict and recommendation."""
        # Insufficient data check
        if creative.leads < 5:
            return ("insufficient_data", "Continue testing - need more conversions")
        
        # Calculate CPL ratio
        if target_cpl > 0 and creative.cpl > 0:
            cpl_ratio = creative.cpl / target_cpl
        else:
            cpl_ratio = 0
        
        # Winner check
        if cpl_ratio <= 0.8 and creative.leads >= 10:
            return ("winner", "Scale this creative - performing above target")
        
        # Underperformer check
        if cpl_ratio >= 2.0 and creative.spend >= 100:
            return ("underperformer", "Consider pausing - CPL is 2x+ target")
        
        # Testing
        if creative.status == "active":
            if cpl_ratio > 1.5:
                return ("testing", "Monitor closely - CPL trending high")
            else:
                return ("testing", "On track - continue monitoring")
        
        # Paused
        if creative.status == "paused":
            return ("paused", creative.pause_reason or "Previously paused")
        
        return ("testing", "Continue monitoring")
    
    def _determine_health(self, decision: Decision, metrics: CampaignMetrics) -> str:
        """Determine overall campaign health."""
        if decision.decision_type.value == "learning_phase":
            return "learning"
        
        if decision.decision_type.value in ["pause_creative", "kill_campaign"]:
            return "critical"
        
        if decision.decision_type.value == "wait_for_data":
            return "warning"
        
        if metrics.cpl_ratio <= 1.0:
            return "healthy"
        elif metrics.cpl_ratio <= 1.5:
            return "warning"
        else:
            return "critical"
    
    def _generate_summary(self, metrics: CampaignMetrics, decision: Decision) -> str:
        """Generate executive summary using LLM."""
        prompt = self.SUMMARY_PROMPT.format(
            days_running=metrics.days_running,
            spend=f"{metrics.total_spend:.0f}",
            leads=metrics.total_leads,
            cpl=f"{metrics.cpl:.0f}",
            target_cpl=f"{metrics.target_cpl:.0f}",
            cpl_ratio=metrics.cpl_ratio,
            ctr=metrics.ctr,
            impressions=metrics.impressions,
            decision_type=decision.decision_type.value,
            confidence=decision.confidence.value,
        )
        
        try:
            return self.router.generate(
                task_type=TaskType.ANALYSIS,
                prompt=prompt,
            ).strip()
        except Exception:
            # Fallback summary
            return (
                f"Campaign running for {metrics.days_running} days with "
                f"₹{metrics.total_spend:.0f} spent. "
                f"CPL is ₹{metrics.cpl:.0f} ({metrics.cpl_ratio:.0%} of target). "
                f"Confidence level: {decision.confidence.value}."
            )
    
    def _generate_insights(
        self, 
        metrics: CampaignMetrics, 
        creative_analyses: List[CreativeAnalysis]
    ) -> List[str]:
        """Generate key insights using LLM."""
        # Build creative summary
        creative_lines = []
        for ca in creative_analyses[:5]:
            creative_lines.append(
                f"- {ca.name}: {ca.verdict} (CPL ₹{ca.cpl:.0f}, {ca.leads} leads)"
            )
        creative_summary = "\n".join(creative_lines) if creative_lines else "No creatives tracked"
        
        prompt = self.INSIGHTS_PROMPT.format(
            cpl=f"{metrics.cpl:.0f}",
            target_cpl=f"{metrics.target_cpl:.0f}",
            cpl_ratio=metrics.cpl_ratio,
            ctr=metrics.ctr,
            spend=f"{metrics.total_spend:.0f}",
            leads=metrics.total_leads,
            days_running=metrics.days_running,
            creative_summary=creative_summary,
        )
        
        try:
            response = self.router.generate(
                task_type=TaskType.ANALYSIS,
                prompt=prompt,
            )
            insights = [i.strip() for i in response.strip().split("\n") if i.strip()]
            return insights[:5]
        except Exception:
            # Fallback insights
            return self._fallback_insights(metrics)
    
    def _fallback_insights(self, metrics: CampaignMetrics) -> List[str]:
        """Generate fallback insights without LLM."""
        insights = []
        
        if metrics.cpl_ratio <= 0.8:
            insights.append(f"✅ CPL is {100 - metrics.cpl_ratio*100:.0f}% below target - excellent performance")
        elif metrics.cpl_ratio >= 1.5:
            insights.append(f"⚠️ CPL is {metrics.cpl_ratio*100 - 100:.0f}% above target - needs attention")
        
        if metrics.ctr >= 1.0:
            insights.append(f"✅ CTR of {metrics.ctr:.2f}% is strong")
        elif metrics.ctr < 0.5:
            insights.append(f"⚠️ CTR of {metrics.ctr:.2f}% is below average")
        
        if metrics.total_leads < 10:
            insights.append("📊 Need more leads for reliable analysis")
        
        if metrics.days_running < 3:
            insights.append("🎯 Still in learning phase - avoid major changes")
        
        return insights if insights else ["📊 Monitoring campaign performance"]
    
    def _assess_data_quality(
        self, 
        metrics: CampaignMetrics, 
        state: CampaignState
    ) -> List[str]:
        """Assess data quality and return notes."""
        notes = []
        
        if metrics.total_leads < 10:
            notes.append("⚠️ Low lead volume - decisions have low confidence")
        
        if metrics.days_running < 3:
            notes.append("ℹ️ Campaign in learning phase - data is preliminary")
        
        if metrics.total_spend < 100:
            notes.append("ℹ️ Limited spend - insufficient for statistical significance")
        
        if state.target_cpl <= 0:
            notes.append("⚠️ No target CPL set - unable to evaluate performance")
        
        if not state.creatives:
            notes.append("ℹ️ No creative-level data available")
        
        if not notes:
            notes.append("✅ Data quality is sufficient for analysis")
        
        return notes
    
    def quick_health_check(self, state: CampaignState) -> Dict[str, Any]:
        """
        Perform a quick health check without full analysis.
        
        Returns simple status and key metrics.
        """
        metrics = self._build_metrics(state)
        decision = self.rules.evaluate(metrics)
        health = self._determine_health(decision, metrics)
        confidence = self.rules.get_confidence_level(metrics.total_leads)
        
        return {
            "health": health,
            "confidence": confidence.value,
            "cpl": metrics.cpl,
            "target_cpl": metrics.target_cpl,
            "cpl_ratio": metrics.cpl_ratio,
            "decision": decision.decision_type.value,
            "leads": metrics.total_leads,
            "spend": metrics.total_spend,
            "days": metrics.days_running,
        }


# Singleton instance
_analysis_agent: Optional[AnalysisAgent] = None


def get_analysis_agent() -> AnalysisAgent:
    """Get or create the analysis agent singleton."""
    global _analysis_agent
    if _analysis_agent is None:
        _analysis_agent = AnalysisAgent()
    return _analysis_agent
