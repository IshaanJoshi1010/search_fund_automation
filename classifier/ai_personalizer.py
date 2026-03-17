import logging
import os
import json

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Initialize the model once
_model = None

def _get_model():
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "your_gemini_api_key_here":
            return None
        genai.configure(api_key=api_key)
        # Using a fast and capable model for structured JSON output
        _model = genai.GenerativeModel("gemini-1.5-flash")
    return _model

def generate_hooks(
    first_name: str,
    city: str,
    state: str,
    bio_text: str,
    fallback_rel_hook: str,
    fallback_focus_hook: str
) -> tuple[str, str]:
    """
    Uses Gemini to generate bespoke `relationship_hook` and `focus_hook` text 
    based on the searcher's parsed bio text and location.
    
    Returns standard fallback rule-based hooks if API fails or is not configured.
    """
    model = _get_model()
    if not model:
        logger.debug("Gemini API key not configured. Using rule-based fallback hooks.")
        return fallback_rel_hook, fallback_focus_hook
        
    if not bio_text or len(bio_text) < 20:
        return fallback_rel_hook, fallback_focus_hook

    prompt = f"""
You are an AI assistant helping a high school senior craft highly personalized email outreach to search fund investors.

The email templates have two specific blanks we need to fill:

Template line 1:
"I wanted to connect with a [RELATIONSHIP_HOOK] who has actually done the search fund path successfully."

Template line 2: 
"I know you focus heavily on the [FOCUS_HOOK] now. I would be grateful for the opportunity..."

Here is the data for the target searcher:
Name: {first_name}
Location: {city}, {state}
Bio/Background:
{bio_text[:1500]}

Your task: Read the background and generate extremely natural, conversational replacements for those two hooks. 

Rules for RELATIONSHIP_HOOK:
1. If they are in the US Mid-Atlantic (PA, NJ, NY, DE, MD, VA), use a local neighbor angle (e.g., 'Philadelphia-area neighbor').
2. Otherwise, look for an interesting similarity or just call them a 'seasoned ETA operator' or 'successful traditional searcher'. 
3. MUST NOT disrupt the surrounding grammar.

Rules for FOCUS_HOOK:
1. Identify the EXACT type of companies they buy or are looking for (e.g., 'b2b software and tech-enabled services space', 'healthcare IT sector', 'lower middle market industrials space').
2. Keep it under 10 words. Must flow naturally into the sentence.

Return ONLY a valid JSON object strictly matching this format:
{{
    "relationship_hook": "...",
    "focus_hook": "..."
}}
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        
        data = json.loads(response.text)
        
        rel_hook = data.get("relationship_hook", fallback_rel_hook)
        foc_hook = data.get("focus_hook", fallback_focus_hook)
        
        logger.info(f"✨ AI Hooks generated for {first_name}: {rel_hook} | {foc_hook}")
        return rel_hook, foc_hook
        
    except Exception as e:
        logger.error(f"Gemini API hook generation failed: {e}")
        return fallback_rel_hook, fallback_focus_hook
