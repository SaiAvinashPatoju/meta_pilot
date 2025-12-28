"""
LLM client with grounding enforcement.
Abstracts OpenAI calls and enforces playbook citation requirements.
"""
import re
from typing import List, Dict, Optional
from openai import OpenAI
from app.config import settings
from app.knowledge_base.rules import format_rules_for_prompt, PLAYBOOK_RULES


class LLMClient:
    """Abstracted LLM client with provider swapping capability."""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.llm_model
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with persona and grounding rules."""
        rules_text = format_rules_for_prompt()
        
        return f"""You are a Senior Media Buyer AI assistant trained on Jim's Digital Marketing methodology from the "Learn Meta Ads Step-by-Step" course.

## Your Role
- Answer questions about Meta Ads campaigns based ONLY on the provided context and playbook rules.
- Always cite your sources using [Rule ID] or [Timestamp] format.
- If the answer is not in the provided context or playbook, say "I don't have information about this in the course materials."

## Anti-Hallucination Requirements
1. NEVER make up information not present in the context.
2. ALWAYS cite at least one playbook rule [RULE-ID] or timestamp when giving advice.
3. If asked about something outside Meta Ads, politely redirect to your area of expertise.

{rules_text}

## Response Format
When answering:
1. Provide the answer based on retrieved context
2. Cite the source: either a playbook rule ID or the timestamp from the video
3. If multiple rules apply, cite all of them
"""
    
    def answer_with_context(
        self, 
        query: str, 
        context_snippets: str, 
        source_metadata: List[Dict]
    ) -> Dict:
        """
        Generate an answer using retrieved context with grounding enforcement.
        
        Args:
            query: User's question
            context_snippets: Formatted context from vector search
            source_metadata: Metadata from retrieved chunks for citation
            
        Returns:
            Dict with answer, citations, and grounding status
        """
        # Build user message with context
        user_message = f"""## Retrieved Context from Video Course
{context_snippets}

## User Question
{query}

Please provide an answer based on the above context, citing relevant rule IDs and/or timestamps."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,  # Lower temperature for factual answers
            max_tokens=1000
        )
        
        answer = response.choices[0].message.content
        
        # Check for grounding (must cite at least one rule or timestamp)
        grounding_check = self._verify_grounding(answer)
        
        if not grounding_check["is_grounded"]:
            # Return abstain message if no citations
            return {
                "answer": "I cannot provide a confident answer without citing specific course materials. Please rephrase your question or ask about a specific Meta Ads topic covered in Jim's course.",
                "citations": [],
                "grounded": False,
                "abstained": True
            }
        
        return {
            "answer": answer,
            "citations": grounding_check["citations"],
            "grounded": True,
            "abstained": False
        }
    
    def _verify_grounding(self, answer: str) -> Dict:
        """
        Verify that the answer contains proper citations.
        
        Returns:
            Dict with is_grounded bool and list of found citations
        """
        # Pattern to match rule IDs like [COPY-001], [CAMP-002], etc.
        rule_pattern = r'\[([A-Z]+-\d+)\]'
        # Pattern to match timestamps like [07:58:00] or [Timestamp: 07:58:00]
        timestamp_pattern = r'\[(?:Timestamp:\s*)?(\d{1,2}:\d{2}:\d{2})\]'
        
        found_rules = re.findall(rule_pattern, answer)
        found_timestamps = re.findall(timestamp_pattern, answer)
        
        # Validate that found rules are real playbook rules
        valid_rule_ids = {r.id for r in PLAYBOOK_RULES}
        valid_citations = [r for r in found_rules if r in valid_rule_ids]
        
        citations = {
            "rule_ids": valid_citations,
            "timestamps": found_timestamps
        }
        
        is_grounded = len(valid_citations) > 0 or len(found_timestamps) > 0
        
        return {
            "is_grounded": is_grounded,
            "citations": citations
        }


# Singleton instance for FastAPI
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def answer_with_context(query: str, context_snippets: str, source_metadata: List[Dict]) -> Dict:
    """Convenience function for answering with context."""
    client = get_llm_client()
    return client.answer_with_context(query, context_snippets, source_metadata)
