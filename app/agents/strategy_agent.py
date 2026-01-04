"""
Strategy Agent for MetaPilot.
Applies rules engine decisions and uses LLM to explain them.

Key principle: Rules engine MAKES decisions, LLM EXPLAINS them.
"""
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.engine.model_router import ModelRouter, TaskType, get_model_router
from app.engine.rules_engine import RulesEngine, Decision, CampaignMetrics, get_rules_engine
from app.engine.state_store import CampaignState


@dataclass
class StrategyResponse:
    """Response from the strategy agent."""
    decision: Decision
    explanation: str
    action_items: List[str]
    warnings: List[str]
    next_steps: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.to_dict(),
            "explanation": self.explanation,
            "action_items": self.action_items,
            "warnings": self.warnings,
            "next_steps": self.next_steps,
        }


class StrategyAgent:
    """
    Agent responsible for campaign strategy decisions.
    
    This agent:
    1. Takes campaign state and metrics
    2. Calls the rules engine to get a deterministic decision
    3. Uses LLM to explain the decision in natural language
    4. DOES NOT override the rules engine decision
    """
    
    EXPLANATION_PROMPT = """You are a media buying expert explaining a campaign decision to a client.

The rules engine has made the following decision:
- Decision Type: {decision_type}
- Confidence Level: {confidence}
- Reasoning: {reasoning}

Campaign Context:
- Product: {product_name}
- Objective: {objective}
- Current CPL: ₹{cpl}
- Target CPL: ₹{target_cpl}
- Days Running: {days_running}
- Total Leads: {leads}
- Total Spend: ₹{spend}

Constraints from rules:
{constraints}

What NOT to do:
{do_not}

Instructions:
1. Explain WHY this decision was made in 2-3 sentences
2. Use conversational language, not technical jargon
3. Reference specific numbers from the data
4. Be direct and actionable
5. Do NOT contradict or soften the decision
6. Include the confidence level naturally

Your explanation:"""

    ACTION_ITEMS_PROMPT = """Based on this campaign decision, list 3-5 specific action items.

Decision: {decision_type}
Reasoning: {reasoning}
Recommendations: {recommendations}

Format as a numbered list of concrete actions the advertiser should take TODAY.
Be specific (include numbers, percentages, timeframes).
"""

    def __init__(
        self, 
        model_router: Optional[ModelRouter] = None,
        rules_engine: Optional[RulesEngine] = None
    ):
        """Initialize the strategy agent."""
        self.router = model_router or get_model_router()
        self.rules = rules_engine or get_rules_engine()
    
    def evaluate_campaign(
        self, 
        state: CampaignState,
        metrics: Optional[CampaignMetrics] = None
    ) -> StrategyResponse:
        """
        Evaluate campaign and return strategy decision with explanation.
        
        Args:
            state: Current campaign state
            metrics: Optional fresh metrics (if not provided, uses state)
            
        Returns:
            StrategyResponse with decision, explanation, and action items
        """
        # Build metrics from state if not provided
        if metrics is None:
            metrics = CampaignMetrics(
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
        
        # Get decision from rules engine (deterministic)
        decision = self.rules.evaluate(metrics)
        
        # Log decision to state
        state.log_decision(
            decision_type=decision.decision_type.value,
            confidence=decision.confidence.value,
            reasoning=decision.reasoning,
            metrics_snapshot={
                "cpl": metrics.cpl,
                "target_cpl": metrics.target_cpl,
                "spend": metrics.total_spend,
                "leads": metrics.total_leads,
                "days": metrics.days_running,
            }
        )
        
        # Generate natural language explanation using LLM
        explanation = self._generate_explanation(decision, state, metrics)
        
        # Generate action items
        action_items = self._generate_action_items(decision)
        
        # Compile warnings
        warnings = self._compile_warnings(decision, metrics)
        
        # Determine next steps
        next_steps = self._determine_next_steps(decision, state)
        
        return StrategyResponse(
            decision=decision,
            explanation=explanation,
            action_items=action_items,
            warnings=warnings,
            next_steps=next_steps,
        )
    
    def _generate_explanation(
        self, 
        decision: Decision, 
        state: CampaignState,
        metrics: CampaignMetrics
    ) -> str:
        """Generate natural language explanation for the decision."""
        prompt = self.EXPLANATION_PROMPT.format(
            decision_type=decision.decision_type.value,
            confidence=decision.confidence.value,
            reasoning=decision.reasoning,
            product_name=state.product_name or "your product",
            objective=state.objective or "not specified",
            cpl=f"{metrics.cpl:.0f}",
            target_cpl=f"{metrics.target_cpl:.0f}",
            days_running=metrics.days_running,
            leads=metrics.total_leads,
            spend=f"{metrics.total_spend:.0f}",
            constraints="\n".join(f"- {c}" for c in decision.constraints),
            do_not="\n".join(f"- {d}" for d in decision.do_not),
        )
        
        try:
            explanation = self.router.generate(
                task_type=TaskType.STRATEGY,
                prompt=prompt,
            )
            return explanation.strip()
        except Exception as e:
            # Fallback to decision reasoning if LLM fails
            return decision.reasoning
    
    def _generate_action_items(self, decision: Decision) -> List[str]:
        """Generate specific action items based on decision."""
        # Start with recommendations from rules engine
        action_items = list(decision.recommendations)
        
        # Add decision-specific actions
        if decision.decision_type.value == "learning_phase":
            action_items.insert(0, "Monitor campaign but DO NOT make changes")
        elif decision.decision_type.value == "pause_creative":
            action_items.insert(0, "Pause underperforming ad sets immediately")
        elif decision.decision_type.value == "scale_budget":
            if "max_new_budget" in decision.data_points:
                max_budget = decision.data_points["max_new_budget"]
                action_items.insert(0, f"Increase budget to ₹{max_budget:.0f}/day")
        elif decision.decision_type.value == "wait_for_data":
            action_items.insert(0, "Continue running campaign without changes")
        
        return action_items[:5]  # Max 5 items
    
    def _compile_warnings(self, decision: Decision, metrics: CampaignMetrics) -> List[str]:
        """Compile warnings based on decision and metrics."""
        warnings = []
        
        # Add confidence-based warning
        if decision.confidence.value == "insufficient":
            warnings.append("⚠️ Insufficient data for reliable decision-making")
        elif decision.confidence.value == "low":
            warnings.append("⚠️ Low confidence - more data needed for certainty")
        
        # Add metric-specific warnings
        if metrics.ctr < 0.5 and metrics.impressions > 1000:
            warnings.append("⚠️ CTR below 0.5% - creative may need improvement")
        
        if metrics.cpl_ratio > 1.5 and metrics.total_leads >= 10:
            warnings.append("⚠️ CPL is 50%+ above target")
        
        # Always include disclaimer
        warnings.append(f"ℹ️ {decision.disclaimer}")
        
        return warnings
    
    def _determine_next_steps(self, decision: Decision, state: CampaignState) -> List[str]:
        """Determine what should happen next."""
        next_steps = []
        
        if decision.decision_type.value == "learning_phase":
            days_left = 3 - state.days_running
            next_steps.append(f"Check back in {days_left} day(s) after learning phase")
        elif decision.decision_type.value == "wait_for_data":
            next_steps.append("Continue monitoring - reassess when more leads come in")
        elif decision.decision_type.value == "pause_creative":
            next_steps.append("Review paused creatives for learnings")
            next_steps.append("Test new creative angles")
        elif decision.decision_type.value == "scale_budget":
            next_steps.append("Monitor CPL for 24-48 hours after scaling")
            next_steps.append("If CPL rises significantly, reassess")
        else:
            next_steps.append("Review performance again in 24 hours")
        
        return next_steps
    
    def validate_proposed_action(
        self, 
        action: str, 
        state: CampaignState,
        proposed_value: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Validate a proposed action against the rules.
        
        Returns whether the action is allowed and why.
        """
        if action == "budget_increase" and proposed_value:
            return self.rules.validate_budget_change(
                state.daily_budget, 
                float(proposed_value), 
                "increase"
            )
        elif action == "budget_decrease" and proposed_value:
            return self.rules.validate_budget_change(
                state.daily_budget, 
                float(proposed_value), 
                "decrease"
            )
        elif action == "pause_adset":
            if state.days_running < 3:
                return {
                    "allowed": False,
                    "reasoning": "Cannot pause during learning phase (first 3 days)",
                }
            return {"allowed": True, "reasoning": "Pausing allowed"}
        elif action == "change_targeting":
            if state.days_running < 3:
                return {
                    "allowed": False,
                    "reasoning": "Cannot change targeting during learning phase",
                }
            return {"allowed": True, "reasoning": "Targeting changes allowed"}
        
        return {"allowed": True, "reasoning": "Action allowed by default"}


# Singleton instance
_strategy_agent: Optional[StrategyAgent] = None


def get_strategy_agent() -> StrategyAgent:
    """Get or create the strategy agent singleton."""
    global _strategy_agent
    if _strategy_agent is None:
        _strategy_agent = StrategyAgent()
    return _strategy_agent
