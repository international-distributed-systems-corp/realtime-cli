from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import json

class ModelType(Enum):
    """OpenAI model types"""
    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT4O_REALTIME = "gpt-4o-realtime-preview"
    GPT4O_MINI_REALTIME = "gpt-4o-mini-realtime-preview"

@dataclass
class TokenPricing:
    """Token-based pricing structure"""
    input_price: float  # Per 1M tokens
    output_price: float  # Per 1M tokens
    cached_input_price: float  # Per 1M tokens
    audio_input_price: Optional[float] = None  # Per 1M tokens
    audio_output_price: Optional[float] = None  # Per 1M tokens

class PricingTier(Enum):
    """Global pricing tiers"""
    STANDARD = 1.0  # Base pricing
    DISCOUNTED = 0.9  # 10% discount
    PREMIUM = 1.2  # 20% premium

# Base model pricing in USD
MODEL_PRICING = {
    ModelType.GPT4O_REALTIME: TokenPricing(
        input_price=5.00,
        output_price=20.00,
        cached_input_price=2.50,
        audio_input_price=40.00,
        audio_output_price=80.00
    ),
    ModelType.GPT4O_MINI_REALTIME: TokenPricing(
        input_price=0.60,
        output_price=2.40,
        cached_input_price=0.30,
        audio_input_price=10.00,
        audio_output_price=20.00
    )
}

# Regional pricing adjustments
REGION_MULTIPLIERS = {
    "US": 1.0,
    "EU": 1.2,  # 20% premium for EU
    "UK": 1.15,  # 15% premium for UK
    "IN": 0.8,  # 20% discount for India
    "BR": 0.85,  # 15% discount for Brazil
    "DEFAULT": 1.0
}

def get_price_for_region(base_price: float, region_code: str) -> float:
    """Calculate price adjusted for region"""
    multiplier = REGION_MULTIPLIERS.get(region_code, REGION_MULTIPLIERS["DEFAULT"])
    return base_price * multiplier

def calculate_usage_cost(
    model: ModelType,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    audio_input_tokens: int = 0,
    audio_output_tokens: int = 0,
    region_code: str = "US",
    pricing_tier: PricingTier = PricingTier.STANDARD
) -> float:
    """Calculate total cost for usage"""
    pricing = MODEL_PRICING[model]
    
    # Calculate base costs
    input_cost = (input_tokens / 1_000_000) * get_price_for_region(pricing.input_price, region_code)
    output_cost = (output_tokens / 1_000_000) * get_price_for_region(pricing.output_price, region_code)
    cached_cost = (cached_tokens / 1_000_000) * get_price_for_region(pricing.cached_input_price, region_code)
    
    # Add audio costs if applicable
    audio_input_cost = 0
    audio_output_cost = 0
    if pricing.audio_input_price and audio_input_tokens > 0:
        audio_input_cost = (audio_input_tokens / 1_000_000) * get_price_for_region(pricing.audio_input_price, region_code)
    if pricing.audio_output_price and audio_output_tokens > 0:
        audio_output_cost = (audio_output_tokens / 1_000_000) * get_price_for_region(pricing.audio_output_price, region_code)
    
    # Apply pricing tier multiplier
    total = (input_cost + output_cost + cached_cost + audio_input_cost + audio_output_cost) * pricing_tier.value
    
    return round(total, 6)  # Round to 6 decimal places for micro-billing
