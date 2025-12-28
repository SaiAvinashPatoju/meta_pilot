"""
MetaPilot Conversational Agent.
LangChain-based agent with 5 pillars requirement gathering workflow.
"""
import json
import re
import uuid
from typing import Dict, Optional, Tuple
from openai import OpenAI

from app.config import settings
from app.models.campaign import (
    CampaignRequirements,
    ConversationState,
    CampaignObjective,
    BudgetType,
    TargetingInfo,
)
from app.agent.prompts import SYSTEM_PROMPT, PILLAR_PROMPTS, SUMMARY_TEMPLATE
from app.knowledge_base.vector_store import VectorStore
from app.knowledge_base.rules import format_rules_for_prompt


class MetaPilotAgent:
    """
    Conversational agent for gathering campaign requirements.
    Follows Jim's methodology and gathers the 5 Pillars.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
        self._vector_store: Optional[VectorStore] = None
        self.sessions: Dict[str, ConversationState] = {}
    
    @property
    def vector_store(self) -> VectorStore:
        """Lazy load vector store."""
        if self._vector_store is None:
            self._vector_store = VectorStore()
        return self._vector_store
    
    def create_session(self) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = ConversationState(session_id=session_id)
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Get an existing session."""
        return self.sessions.get(session_id)
    
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
            collected += f"- Budget: ${requirements.budget_amount}/{requirements.budget_type.value}\n"
        if requirements.targeting.locations:
            collected += f"- Targeting: {', '.join(requirements.targeting.locations)}\n"
        if requirements.usp:
            collected += f"- USP: {requirements.usp}\n"
        if requirements.product_name:
            collected += f"- Product: {requirements.product_name}\n"
        
        return progress + collected + pillar_guidance
    
    def _extract_requirements(self, message: str, state: ConversationState) -> None:
        """Extract and update requirements from user message."""
        message_lower = message.lower()
        requirements = state.requirements
        
        # Extract objective
        if not requirements.objective:
            if any(word in message_lower for word in ["sales", "purchase", "sell", "buy", "e-commerce", "shopify"]):
                requirements.objective = CampaignObjective.SALES
            elif any(word in message_lower for word in ["lead", "contact", "form", "signup"]):
                requirements.objective = CampaignObjective.LEADS
            elif any(word in message_lower for word in ["traffic", "visit", "click"]):
                requirements.objective = CampaignObjective.TRAFFIC
            elif any(word in message_lower for word in ["engagement", "like", "comment", "share"]):
                requirements.objective = CampaignObjective.ENGAGEMENT
            elif any(word in message_lower for word in ["awareness", "brand", "reach"]):
                requirements.objective = CampaignObjective.AWARENESS
        
        # Extract budget
        if not requirements.budget_amount:
            # Look for dollar amounts
            budget_match = re.search(r'\$?(\d+(?:\.\d{2})?)\s*(?:per\s*)?(?:day|daily)?', message_lower)
            if budget_match:
                requirements.budget_amount = float(budget_match.group(1))
            if "lifetime" in message_lower:
                requirements.budget_type = BudgetType.LIFETIME
            else:
                requirements.budget_type = BudgetType.DAILY
        
        # Extract location
        if not requirements.targeting.locations:
            # Common location patterns
            locations = []
            location_patterns = [
                r'(?:in|target(?:ing)?)\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)',
                r'(?:NY|NYC|LA|SF|Chicago|Miami|Boston)',
            ]
            for pattern in location_patterns:
                matches = re.findall(pattern, message, re.IGNORECASE)
                locations.extend(matches)
            
            # State abbreviations
            states = re.findall(r'\b([A-Z]{2})\b', message)
            locations.extend(states)
            
            if locations:
                requirements.targeting.locations = list(set(locations))
        
        # Extract product name (look for quoted text or "called X")
        if not requirements.product_name:
            # Look for quoted product names
            quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', message)
            if quoted:
                requirements.product_name = quoted[0][0] or quoted[0][1]
            # Look for "called X" or "named X" patterns
            else:
                name_match = re.search(r'(?:called|named|selling|product is|service is)\s+([A-Za-z0-9\s]+?)(?:\.|,|$)', message, re.IGNORECASE)
                if name_match:
                    requirements.product_name = name_match.group(1).strip()
        
        # Extract USP
        if not requirements.usp:
            usp_patterns = [
                r'(?:unique|special|different|best|usp)\s*(?:is|:)?\s*(.+?)(?:\.|$)',
                r'(?:we|our)\s+(?:offer|provide|have)\s+(.+?)(?:\.|$)',
            ]
            for pattern in usp_patterns:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    requirements.usp = match.group(1).strip()
                    # Extract USP keywords
                    words = requirements.usp.split()
                    requirements.usp_keywords = [w for w in words if len(w) > 4][:5]
                    break
        
        # Extract pixel status
        if "pixel" in message_lower:
            if any(word in message_lower for word in ["yes", "installed", "ready", "set up", "have"]):
                requirements.pixel_installed = True
            elif any(word in message_lower for word in ["no", "not", "don't"]):
                requirements.pixel_installed = False
    
    def chat(self, session_id: str, user_message: str) -> Dict:
        """
        Process a user message and return the agent's response.
        
        Returns:
            Dict with 'response', 'requirements', 'complete', and 'phase'
        """
        state = self.get_session(session_id)
        if not state:
            return {"error": "Session not found"}
        
        # Add user message
        state.add_message("user", user_message)
        
        # Extract requirements from message
        self._extract_requirements(user_message, state)
        
        # Check if all pillars are complete
        if state.requirements.is_complete() and state.phase == "gathering":
            state.phase = "review"
        
        # Build the conversation for the LLM
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": self._build_context_prompt(state)},
        ]
        
        # Add conversation history (last 10 messages to avoid token limits)
        for msg in state.messages[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Generate response
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        
        assistant_message = response.choices[0].message.content
        state.add_message("assistant", assistant_message)
        
        return {
            "response": assistant_message,
            "requirements": state.requirements.model_dump(),
            "complete": state.requirements.is_complete(),
            "phase": state.phase,
            "progress": state.requirements.completion_percentage(),
            "missing_pillars": state.requirements.missing_pillars()
        }
    
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
            usp=req.usp or "Not specified",
            pixel_installed=req.pixel_installed
        )


# Singleton instance
_agent: Optional[MetaPilotAgent] = None


def get_agent() -> MetaPilotAgent:
    """Get or create the agent singleton."""
    global _agent
    if _agent is None:
        _agent = MetaPilotAgent()
    return _agent
