"""
Geography classifier.
Given a lead's city/state, derives the appropriate relationship_hook for the email.
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)


def load_geo_config() -> dict:
    cfg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    return config.get("geography", {})


def derive_relationship_hook(city: str | None, state: str | None) -> str:
    """
    Given city and state, return the most specific geographic relationship_hook.

    Priority:
    1. Philadelphia metro city → "Philadelphia-area neighbor"
    2. Mid-Atlantic state → "Mid-Atlantic neighbor"
    3. Fallback → "fellow operator who has taken the search fund journey successfully"
    """
    geo = load_geo_config()
    philly_cities = [c.lower() for c in geo.get("philadelphia_metro_cities", [])]
    mid_atlantic_states = [s.upper() for s in geo.get("mid_atlantic_states", [])]

    city_lower = (city or "").lower().strip()
    state_upper = (state or "").upper().strip()

    # Check Philadelphia metro first (most specific)
    if city_lower and any(city_lower in c or c in city_lower for c in philly_cities):
        return "Philadelphia-area neighbor"

    # Check Mid-Atlantic state
    if state_upper and state_upper in mid_atlantic_states:
        return "Mid-Atlantic neighbor"

    return "fellow operator who has taken the search fund journey successfully"
