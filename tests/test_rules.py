"""
Unit tests for the playbook rules module.
"""
import pytest
from app.knowledge_base.rules import (
    get_all_rules,
    get_rules_by_category,
    get_rule_by_id,
    format_rules_for_prompt,
    validate_description_length,
    validate_headline_has_usp,
    PLAYBOOK_RULES,
)


class TestPlaybookRules:
    """Tests for playbook rule retrieval functions."""
    
    def test_get_all_rules_returns_list(self):
        """Test that get_all_rules returns the full list."""
        rules = get_all_rules()
        assert len(rules) == len(PLAYBOOK_RULES)
        assert len(rules) > 0
    
    def test_rules_have_required_fields(self):
        """Test that all rules have required fields."""
        rules = get_all_rules()
        for rule in rules:
            assert rule.id, "Rule must have an id"
            assert rule.category, "Rule must have a category"
            assert rule.rule, "Rule must have a rule text"
            assert rule.timestamp, "Rule must have a timestamp"
    
    def test_rule_ids_are_unique(self):
        """Test that all rule IDs are unique."""
        rules = get_all_rules()
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids)), "All rule IDs must be unique"
    
    def test_get_rules_by_category(self):
        """Test filtering rules by category."""
        copywriting_rules = get_rules_by_category("copywriting")
        assert len(copywriting_rules) > 0
        assert all(r.category == "copywriting" for r in copywriting_rules)
    
    def test_get_rules_by_invalid_category(self):
        """Test that invalid category returns empty list."""
        rules = get_rules_by_category("nonexistent_category")
        assert rules == []
    
    def test_get_rule_by_id(self):
        """Test retrieving a specific rule by ID."""
        rule = get_rule_by_id("COPY-001")
        assert rule is not None
        assert rule.id == "COPY-001"
        assert "headline" in rule.rule.lower()
    
    def test_get_rule_by_invalid_id(self):
        """Test that invalid ID returns None."""
        rule = get_rule_by_id("INVALID-999")
        assert rule is None


class TestRulesFormatting:
    """Tests for prompt formatting functions."""
    
    def test_format_rules_for_prompt(self):
        """Test that rules are formatted correctly for LLM prompt."""
        formatted = format_rules_for_prompt()
        
        assert "Playbook Rules" in formatted
        assert "[COPY-001]" in formatted
        assert "copywriting" in formatted
        assert "Timestamp:" in formatted
    
    def test_format_specific_rules(self):
        """Test formatting a subset of rules."""
        rules = get_rules_by_category("budget")
        formatted = format_rules_for_prompt(rules)
        
        assert "BUDGET-001" in formatted
        assert "COPY-001" not in formatted  # Should not include copywriting rules


class TestDescriptionValidation:
    """Tests for description length validation (COPY-002)."""
    
    def test_valid_short_description(self):
        """Test that descriptions under 5 words pass."""
        result = validate_description_length("Shop Now")
        assert result["valid"] == True
        assert result["word_count"] == 2
        assert result["rule_id"] == "COPY-002"
    
    def test_valid_four_word_description(self):
        """Test that 4-word descriptions pass."""
        result = validate_description_length("Roasted Daily. Free Shipping.")
        # "Roasted Daily. Free Shipping." = 4 words
        assert result["valid"] == True
        assert result["word_count"] == 4
    
    def test_invalid_five_word_description(self):
        """Test that 5-word descriptions fail."""
        result = validate_description_length("This has exactly five words")
        assert result["valid"] == False
        assert result["word_count"] == 5
    
    def test_invalid_long_description(self):
        """Test that long descriptions fail."""
        result = validate_description_length("This is a very long description that violates the rules")
        assert result["valid"] == False
        assert result["word_count"] > 5
    
    def test_empty_description(self):
        """Test that empty description is valid (0 words)."""
        result = validate_description_length("")
        assert result["valid"] == True
        assert result["word_count"] == 0


class TestHeadlineValidation:
    """Tests for headline USP validation (COPY-001)."""
    
    def test_headline_with_usp(self):
        """Test headline containing USP keywords."""
        result = validate_headline_has_usp(
            "NY's Freshest Organic Roast",
            ["organic", "fresh", "local"]
        )
        assert result["valid"] == True
        assert "organic" in result["found_keywords"]
    
    def test_headline_without_usp(self):
        """Test headline missing USP keywords."""
        result = validate_headline_has_usp(
            "Buy Our Coffee Today",
            ["organic", "fresh", "local"]
        )
        assert result["valid"] == False
        assert result["found_keywords"] == []
    
    def test_case_insensitive_matching(self):
        """Test that USP matching is case insensitive."""
        result = validate_headline_has_usp(
            "ORGANIC Coffee Beans",
            ["organic"]
        )
        assert result["valid"] == True
    
    def test_multiple_usp_matches(self):
        """Test headline with multiple USP keywords."""
        result = validate_headline_has_usp(
            "Fresh Organic Local Coffee",
            ["organic", "fresh", "local"]
        )
        assert result["valid"] == True
        assert len(result["found_keywords"]) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
