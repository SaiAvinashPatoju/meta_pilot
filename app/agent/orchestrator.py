"""
MetaPilot Orchestrator Agent.
Production-ready multi-agent architecture that delegates to specialized agents.

Architecture:
- IntakeAgent: Validates inputs, extracts structured data
- StrategyAgent: Applies rules engine decisions
- CreativeAgent: Generates ad copy (isolated from performance data)
- AnalysisAgent: Analyzes campaign performance

Key principle: Rules engine MAKES decisions, LLMs EXPLAIN them.
"""
import uuid
from typing import Dict, Optional, List, Any
from google import genai

from app.config import settings
from app.models.campaign import (
    CampaignRequirements,
    ConversationState,
    CampaignObjective,
    BudgetType,
)
from app.agent.prompts import SYSTEM_PROMPT, PILLAR_PROMPTS, SUMMARY_TEMPLATE
from app.knowledge_base.vector_store import VectorStore

# Import specialized agents
from app.agents.intake_agent import IntakeAgent, get_intake_agent
from app.agents.strategy_agent import StrategyAgent, get_strategy_agent
from app.agents.creative_agent import CreativeAgent, get_creative_agent
from app.agents.analysis_agent import AnalysisAgent, get_analysis_agent

# Import engine components
from app.engine.state_store import StateStore, CampaignState, get_state_store
from app.engine.rules_engine import RulesEngine, CampaignMetrics, get_rules_engine
from app.engine.model_router import ModelRouter, TaskType, get_model_router


class MetaPilotOrchestrator:
    """
    Production-ready orchestrator that delegates to specialized agents.
    
    This replaces the single-LLM approach with a modular architecture:
    1. IntakeAgent handles input validation and extraction
    2. StrategyAgent applies rules engine for decisions
    3. CreativeAgent generates copy (isolated)
    4. AnalysisAgent provides performance insights
    
    The orchestrator:
    - Maintains conversation state
    - Routes requests to appropriate agents
    - Ensures rules engine authority over decisions
    - Provides consistent user experience
    """
    
    def __init__(self):
        """Initialize the orchestrator with all components."""
        # Core LLM client for conversation
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.llm_model
        
        # Specialized agents (lazy-loaded singletons)
        self._intake_agent: Optional[IntakeAgent] = None
        self._strategy_agent: Optional[StrategyAgent] = None
        self._creative_agent: Optional[CreativeAgent] = None
        self._analysis_agent: Optional[AnalysisAgent] = None
        
        # Engine components
        self._state_store: Optional[StateStore] = None
        self._rules_engine: Optional[RulesEngine] = None
        self._model_router: Optional[ModelRouter] = None
        self._vector_store: Optional[VectorStore] = None
        
        # Session management (in-memory for backward compatibility)
        self.sessions: Dict[str, ConversationState] = {}
        self.campaign_states: Dict[str, CampaignState] = {}
    
    # Lazy-loaded properties
    @property
    def intake_agent(self) -> IntakeAgent:
        if self._intake_agent is None:
            self._intake_agent = get_intake_agent()
        return self._intake_agent
    
    @property
    def strategy_agent(self) -> StrategyAgent:
        if self._strategy_agent is None:
            self._strategy_agent = get_strategy_agent()
        return self._strategy_agent
    
    @property
    def creative_agent(self) -> CreativeAgent:
        if self._creative_agent is None:
            self._creative_agent = get_creative_agent()
        return self._creative_agent
    
    @property
    def analysis_agent(self) -> AnalysisAgent:
        if self._analysis_agent is None:
            self._analysis_agent = get_analysis_agent()
        return self._analysis_agent
    
    @property
    def state_store(self) -> StateStore:
        if self._state_store is None:
            self._state_store = get_state_store()
        return self._state_store
    
    @property
    def rules_engine(self) -> RulesEngine:
        if self._rules_engine is None:
            self._rules_engine = get_rules_engine()
        return self._rules_engine
    
    @property
    def model_router(self) -> ModelRouter:
        if self._model_router is None:
            self._model_router = get_model_router()
        return self._model_router
    
    @property
    def vector_store(self) -> VectorStore:
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store
    
    def create_session(self, targeting_preset: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new conversation session with optional targeting preset.
        
        Args:
            targeting_preset: Optional dict with preset targeting values
            
        Returns:
            session_id
        """
        session_id = str(uuid.uuid4())
        
        # Create conversation state (backward compatibility)
        self.sessions[session_id] = ConversationState(session_id=session_id)
        
        # Create campaign state (new architecture)
        campaign_state = self.state_store.create(session_id)
        self.campaign_states[session_id] = campaign_state
        
        # Apply targeting preset if provided
        if targeting_preset:
            self._apply_targeting_preset(session_id, targeting_preset)
        
        return session_id
    
    def _apply_targeting_preset(self, session_id: str, preset: Dict[str, Any]) -> None:
        """Apply targeting preset to session."""
        conv_state = self.sessions.get(session_id)
        camp_state = self.campaign_states.get(session_id)
        
        if not conv_state or not camp_state:
            return
        
        # Apply to conversation state (backward compatibility)
        if "locations" in preset:
            conv_state.requirements.targeting.locations = preset["locations"]
        if "age_min" in preset:
            conv_state.requirements.targeting.age_min = preset["age_min"]
        if "age_max" in preset:
            conv_state.requirements.targeting.age_max = preset["age_max"]
        if "interests" in preset:
            conv_state.requirements.targeting.interests = preset["interests"]
        if "behaviors" in preset:
            conv_state.requirements.targeting.behaviors = preset["behaviors"]
        if "exclusions" in preset:
            conv_state.requirements.targeting.exclusions = preset["exclusions"]
        
        # Apply to campaign state (new architecture)
        camp_state.locations = preset.get("locations", [])
        camp_state.age_min = preset.get("age_min", 18)
        camp_state.age_max = preset.get("age_max", 65)
        camp_state.interests = preset.get("interests", [])
        camp_state.behaviors = preset.get("behaviors", [])
        camp_state.exclusions = preset.get("exclusions", [])
        
        # Save campaign state
        self.state_store.save(camp_state)
    
    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Get an existing session."""
        return self.sessions.get(session_id)
    
    def get_campaign_state(self, session_id: str) -> Optional[CampaignState]:
        """Get the campaign state for a session."""
        if session_id not in self.campaign_states:
            # Try to load from state store
            camp_state = self.state_store.get_by_session(session_id)
            if camp_state:
                self.campaign_states[session_id] = camp_state
        return self.campaign_states.get(session_id)
    
    def chat(self, session_id: str, user_message: str) -> Dict:
        """
        Process a user message using the multi-agent architecture.
        
        Flow:
        1. IntakeAgent validates and extracts structured data
        2. Update campaign state
        3. Check if requirements complete
        4. Generate conversational response
        
        Returns:
            Dict with 'response', 'requirements', 'complete', 'phase', etc.
        """
        conv_state = self.get_session(session_id)
        camp_state = self.get_campaign_state(session_id)
        
        if not conv_state:
            return {"error": "Session not found"}
        
        # Add user message to conversation history
        conv_state.add_message("user", user_message)
        
        # Step 1: Use IntakeAgent to validate and extract data
        validation = self.intake_agent.validate_and_extract(user_message, camp_state)
        
        # Step 2: Update states with extracted data
        self._update_states_from_extraction(conv_state, camp_state, validation.normalized_values)
        
        # Step 3: Check if all pillars are complete
        if conv_state.requirements.is_complete() and conv_state.phase == "gathering":
            conv_state.phase = "review"
        
        # Step 4: Determine response strategy
        response = self._generate_response(
            conv_state, 
            camp_state, 
            user_message, 
            validation
        )
        
        # Add assistant response to history
        conv_state.add_message("assistant", response)
        
        # Save campaign state
        if camp_state:
            self.state_store.save(camp_state)
        
        return {
            "response": response,
            "requirements": conv_state.requirements.model_dump(),
            "complete": conv_state.requirements.is_complete(),
            "phase": conv_state.phase,
            "progress": conv_state.requirements.completion_percentage(),
            "missing_pillars": conv_state.requirements.missing_pillars(),
            "extraction_confidence": validation.confidence,
            "clarification_needed": validation.clarification_needed,
        }
    
    def _update_states_from_extraction(
        self, 
        conv_state: ConversationState,
        camp_state: Optional[CampaignState],
        extracted: Dict[str, Any]
    ) -> None:
        """Update both states from intake agent extraction."""
        req = conv_state.requirements
        
        # Update conversation state (backward compatibility)
        if "objective" in extracted:
            req.objective = CampaignObjective(extracted["objective"])
        if "daily_budget" in extracted:
            req.budget_amount = extracted["daily_budget"]
        if "locations" in extracted:
            req.targeting.locations = extracted["locations"]
        if "age_min" in extracted:
            req.targeting.age_min = extracted["age_min"]
        if "age_max" in extracted:
            req.targeting.age_max = extracted["age_max"]
        if "interests" in extracted:
            req.targeting.interests = extracted["interests"]
        if "behaviors" in extracted:
            req.targeting.behaviors = extracted["behaviors"]
        if "exclusions" in extracted:
            req.targeting.exclusions = extracted["exclusions"]
        if "product_name" in extracted:
            req.product_name = extracted["product_name"]
        if "usp" in extracted:
            req.usp = extracted["usp"]
        if "pixel_installed" in extracted:
            req.pixel_installed = extracted["pixel_installed"]
        
        # Update campaign state (new architecture)
        if camp_state:
            if "objective" in extracted:
                camp_state.objective = extracted["objective"]
            if "daily_budget" in extracted:
                camp_state.daily_budget = extracted["daily_budget"]
            if "locations" in extracted:
                camp_state.locations = extracted["locations"]
            if "age_min" in extracted:
                camp_state.age_min = extracted["age_min"]
            if "age_max" in extracted:
                camp_state.age_max = extracted["age_max"]
            if "interests" in extracted:
                camp_state.interests = extracted["interests"]
            if "behaviors" in extracted:
                camp_state.behaviors = extracted["behaviors"]
            if "exclusions" in extracted:
                camp_state.exclusions = extracted["exclusions"]
            if "product_name" in extracted:
                camp_state.product_name = extracted["product_name"]
            if "usp" in extracted:
                camp_state.usp = extracted["usp"]
            if "pixel_installed" in extracted:
                camp_state.pixel_installed = extracted["pixel_installed"]
    
    def _generate_response(
        self,
        conv_state: ConversationState,
        camp_state: Optional[CampaignState],
        user_message: str,
        validation: Any
    ) -> str:
        """Generate conversational response using model router."""
        # Check for clarification needs first
        if validation.clarification_needed:
            clarification_field = validation.clarification_needed[0]
            return self.intake_agent.generate_clarification_question(
                clarification_field, 
                camp_state
            )
        
        # Check for missing fields
        if validation.missing_fields and not validation.extracted_data:
            missing_field = validation.missing_fields[0]
            return self.intake_agent.generate_clarification_question(
                missing_field,
                camp_state
            )
        
        # Retrieve RAG context
        rag_context = self._get_rag_context(user_message)
        
        # Build context prompt
        context_prompt = self._build_context_prompt(conv_state)
        
        # Build full prompt
        system_content = SYSTEM_PROMPT + "\n\n" + rag_context + context_prompt
        
        # Format conversation history
        conversation_text = ""
        for msg in conv_state.messages[-10:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            conversation_text += f"\n{role}: {msg['content']}\n"
        
        full_prompt = f"{system_content}\n\n## Conversation\n{conversation_text}\n\nAssistant:"
        
        # Generate response using model router
        try:
            response = self.model_router.generate(
                task_type=TaskType.INTAKE,
                prompt=full_prompt,
                override_config={"max_output_tokens": 1000}
            )
            return response.strip()
        except Exception as e:
            # Fallback to direct client
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config={
                    "temperature": 0.4,
                    "max_output_tokens": 1000,
                }
            )
            return response.text
    
    def _get_rag_context(self, query: str) -> str:
        """Retrieve relevant context from knowledge base."""
        rag_context = ""
        try:
            results = self.vector_store.query(query, top_k=3)
            if results and len(results) > 0:
                rag_context = "\n\n## Relevant Course Insights\n"
                for r in results:
                    timestamp = r.get('metadata', {}).get('timestamp_str', '')
                    text = r.get('text', r.get('metadata', {}).get('text', ''))
                    if text:
                        snippet = f"{text[:300]}..." if len(text) > 300 else text
                        rag_context += f"- [{timestamp}] {snippet}\n"
        except Exception:
            pass
        return rag_context
    
    def _build_context_prompt(self, state: ConversationState) -> str:
        """Build context for the current conversation state."""
        requirements = state.requirements
        
        # Current progress
        progress = f"Progress: {requirements.completion_percentage()}% complete\n"
        progress += f"Missing pillars: {', '.join(requirements.missing_pillars()) or 'None'}\n"
        
        # Current pillar to focus on
        next_pillar = state.get_next_pillar()
        pillar_guidance = ""
        if next_pillar and next_pillar in PILLAR_PROMPTS:
            pillar_guidance = f"\n## Current Focus: {next_pillar.upper()}\n{PILLAR_PROMPTS[next_pillar]}"
        
        # Collected info so far
        collected = "\n## Already Collected:\n"
        if requirements.objective:
            collected += f"- Objective: {requirements.objective.value}\n"
        if requirements.budget_amount:
            collected += f"- Budget: ₹{requirements.budget_amount}/{requirements.budget_type.value}\n"
        if requirements.targeting.locations:
            collected += f"- Locations: {', '.join(requirements.targeting.locations)}\n"
        if requirements.targeting.age_min != 18 or requirements.targeting.age_max != 65:
            collected += f"- Age Range: {requirements.targeting.age_min}-{requirements.targeting.age_max}\n"
        if requirements.targeting.interests:
            collected += f"- Interests: {', '.join(requirements.targeting.interests)}\n"
        if requirements.targeting.behaviors:
            collected += f"- Behaviors: {', '.join(requirements.targeting.behaviors)}\n"
        if requirements.targeting.exclusions:
            collected += f"- Exclusions: {', '.join(requirements.targeting.exclusions)}\n"
        if requirements.usp:
            collected += f"- USP: {requirements.usp}\n"
        if requirements.product_name:
            collected += f"- Product: {requirements.product_name}\n"
        
        return progress + collected + pillar_guidance
    
    def get_welcome_message(self, session_id: str) -> str:
        """Get the initial welcome message for a new session."""
        return """👋 **Hi, I'm MetaPilot - your AI Media Buyer!**

I'm trained on Jim's Digital Marketing methodology and I'm here to help you build an effective Meta Ads campaign.

To create the perfect campaign, I need to gather **5 key pieces of information**:

1. 🎯 **Objective** - What's your campaign goal?
2. 💰 **Budget** - How much do you want to spend?
3. 🎯 **Targeting** - Who's your ideal customer?
4. ⭐ **USP** - What makes your product unique?
5. 📸 **Product & Creative** - What are we advertising?

Let's start! **What product or service are you looking to advertise today?**"""
    
    def generate_summary(self, session_id: str) -> str:
        """Generate a summary of collected requirements."""
        state = self.get_session(session_id)
        if not state:
            return "Session not found"
        
        req = state.requirements
        return SUMMARY_TEMPLATE.format(
            product_name=req.product_name or "Not specified",
            objective=req.objective.value if req.objective else "Not specified",
            budget_amount=req.budget_amount or 0,
            budget_type=req.budget_type.value,
            locations=", ".join(req.targeting.locations) or "Not specified",
            age_min=req.targeting.age_min,
            age_max=req.targeting.age_max,
            interests=", ".join(req.targeting.interests) or "Not specified",
            behaviors=", ".join(req.targeting.behaviors) or "Not specified",
            exclusions=", ".join(req.targeting.exclusions) or "None",
            usp=req.usp or "Not specified",
            pixel_installed=req.pixel_installed
        )
    
    # === New Production Methods ===
    
    def generate_creative(self, session_id: str, context: Optional[Dict] = None) -> Dict:
        """
        Generate ad creative using the creative agent.
        
        Args:
            session_id: Session ID
            context: Optional additional context (pain points, benefits)
            
        Returns:
            Dict with headlines, primary_texts, descriptions, etc.
        """
        camp_state = self.get_campaign_state(session_id)
        if not camp_state:
            return {"error": "Campaign state not found"}
        
        creative_output = self.creative_agent.generate_creative(camp_state, context)
        return creative_output.to_dict()
    
    def analyze_campaign(
        self, 
        session_id: str, 
        metrics: Optional[Dict] = None
    ) -> Dict:
        """
        Analyze campaign performance using the analysis agent.
        
        Args:
            session_id: Session ID
            metrics: Optional fresh metrics from Meta API
            
        Returns:
            Analysis report dict
        """
        camp_state = self.get_campaign_state(session_id)
        if not camp_state:
            return {"error": "Campaign state not found"}
        
        report = self.analysis_agent.analyze_campaign(camp_state, metrics)
        return report.to_dict()
    
    def get_strategy_decision(
        self, 
        session_id: str,
        metrics: Optional[Dict] = None
    ) -> Dict:
        """
        Get strategy decision from rules engine with explanation.
        
        Args:
            session_id: Session ID
            metrics: Optional metrics dict
            
        Returns:
            Strategy response with decision, explanation, action items
        """
        camp_state = self.get_campaign_state(session_id)
        if not camp_state:
            return {"error": "Campaign state not found"}
        
        # Update campaign state with metrics if provided
        if metrics:
            camp_state.current_spend = metrics.get("spend", camp_state.current_spend)
            camp_state.current_leads = metrics.get("leads", camp_state.current_leads)
            camp_state.current_cpl = metrics.get("cpl", camp_state.current_cpl)
            camp_state.current_ctr = metrics.get("ctr", camp_state.current_ctr)
            camp_state.days_running = metrics.get("days_running", camp_state.days_running)
            camp_state.target_cpl = metrics.get("target_cpl", camp_state.target_cpl)
        
        response = self.strategy_agent.evaluate_campaign(camp_state)
        
        # Save updated state
        self.state_store.save(camp_state)
        
        return response.to_dict()
    
    def validate_action(
        self, 
        session_id: str, 
        action: str, 
        value: Optional[Any] = None
    ) -> Dict:
        """
        Validate a proposed action against the rules engine.
        
        Args:
            session_id: Session ID
            action: Action type (budget_increase, budget_decrease, pause_adset, etc.)
            value: Optional value for the action
            
        Returns:
            Validation result with allowed/not allowed and reasoning
        """
        camp_state = self.get_campaign_state(session_id)
        if not camp_state:
            return {"error": "Campaign state not found"}
        
        return self.strategy_agent.validate_proposed_action(action, camp_state, value)


# Singleton instance
_orchestrator: Optional[MetaPilotOrchestrator] = None


def get_orchestrator() -> MetaPilotOrchestrator:
    """Get or create the orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MetaPilotOrchestrator()
    return _orchestrator


# Backward compatibility alias
def get_agent() -> MetaPilotOrchestrator:
    """Backward compatibility: get_agent returns the orchestrator."""
    return get_orchestrator()
