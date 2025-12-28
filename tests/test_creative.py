"""
Unit tests for the creative generators.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestHeadlineGenerator:
    """Tests for headline generation."""
    
    def test_headline_result_model(self):
        """Test HeadlineResult model structure."""
        from app.creative.headline_gen import HeadlineResult
        
        result = HeadlineResult(
            headlines=["Test Headline 1", "Test Headline 2"],
            usp_keywords=["test", "product"],
            validation=[{"headline": "Test", "valid": True}]
        )
        
        assert len(result.headlines) == 2
        assert "COPY-001" in result.rule_citations
    
    def test_validate_headline_length(self):
        """Test that headline length is checked."""
        from app.knowledge_base.rules import validate_headline_has_usp
        
        # Short headline with USP
        result = validate_headline_has_usp("Fresh Organic Coffee", ["fresh", "organic"])
        assert result["valid"] == True
        assert "fresh" in result["found_keywords"] or "organic" in result["found_keywords"]
        
        # Headline without USP keywords
        result = validate_headline_has_usp("Buy Now Today", ["fresh", "organic"])
        assert result["valid"] == False


class TestDescriptionGenerator:
    """Tests for description generation."""
    
    def test_description_result_model(self):
        """Test DescriptionResult model structure."""
        from app.creative.description_gen import DescriptionResult
        
        result = DescriptionResult(
            descriptions=["Shop Now", "Free Shipping"],
            validation=[{"description": "Shop Now", "valid": True, "word_count": 2}]
        )
        
        assert len(result.descriptions) == 2
        assert "COPY-002" in result.rule_citations
    
    def test_description_word_count_validation(self):
        """Test that descriptions are validated for word count."""
        from app.knowledge_base.rules import validate_description_length
        
        # Valid: under 5 words
        result = validate_description_length("Free Shipping Today")
        assert result["valid"] == True
        assert result["word_count"] == 3
        
        # Valid: exactly 4 words
        result = validate_description_length("Shop Now Save Big")
        assert result["valid"] == True
        assert result["word_count"] == 4
        
        # Invalid: 5 words
        result = validate_description_length("One Two Three Four Five")
        assert result["valid"] == False
        assert result["word_count"] == 5
        
        # Invalid: more than 5 words
        result = validate_description_length("This is a very long description text")
        assert result["valid"] == False


class TestPrimaryTextGenerator:
    """Tests for primary text generation."""
    
    def test_primary_text_result_model(self):
        """Test PrimaryTextResult model structure."""
        from app.creative.primary_text_gen import PrimaryTextResult
        
        result = PrimaryTextResult(
            variations=["Sample body copy with PAS framework."],
            framework="PAS"
        )
        
        assert result.framework == "PAS"
        assert "COPY-004" in result.rule_citations


class TestCampaignPlanner:
    """Tests for campaign planning."""
    
    def test_campaign_plan_model(self):
        """Test CampaignPlan model structure."""
        from app.strategy.campaign_planner import CampaignPlan, AdSetConfig
        
        ad_set = AdSetConfig(
            name="Prospecting",
            audience_type="cold",
            targeting={"locations": ["NY"]},
            budget_percentage=0.7
        )
        
        plan = CampaignPlan(
            campaign_name="Test_Campaign",
            objective="OUTCOME_SALES",
            daily_budget=50.0,
            ad_sets=[ad_set]
        )
        
        assert plan.campaign_name == "Test_Campaign"
        assert len(plan.ad_sets) == 1
        assert plan.ad_sets[0].audience_type == "cold"
    
    def test_planner_generates_cold_and_warm_adsets(self):
        """Test that planner creates both cold and retargeting ad sets."""
        from app.strategy.campaign_planner import CampaignPlanner
        from app.models.campaign import CampaignRequirements, CampaignObjective, TargetingInfo
        
        planner = CampaignPlanner()
        
        requirements = CampaignRequirements(
            objective=CampaignObjective.SALES,
            budget_amount=50.0,
            targeting=TargetingInfo(locations=["New York"]),
            usp="Best coffee in town",
            product_name="Organic Coffee"
        )
        
        plan = planner.generate_plan(requirements)
        
        assert len(plan.ad_sets) == 2
        audience_types = [a.audience_type for a in plan.ad_sets]
        assert "cold" in audience_types
        assert "retargeting" in audience_types
    
    def test_budget_recommendations(self):
        """Test budget-related recommendations."""
        from app.strategy.campaign_planner import CampaignPlanner
        from app.models.campaign import CampaignRequirements, CampaignObjective, TargetingInfo
        
        planner = CampaignPlanner()
        
        # Low budget should generate warning
        requirements = CampaignRequirements(
            objective=CampaignObjective.SALES,
            budget_amount=5.0,  # Below recommended
            targeting=TargetingInfo(locations=["NY"]),
            usp="Test USP",
            product_name="Test Product"
        )
        
        plan = planner.generate_plan(requirements)
        
        assert any("BUDGET-001" in w for w in plan.warnings) or "BUDGET-001" in plan.rule_citations


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
