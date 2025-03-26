"""
Agent-related modules for the fact extraction system.
"""

from src.agents.prompts import FACT_EXTRACTOR_PROMPT, FACT_VERIFICATION_PROMPT
from src.agents.verification import FactVerificationAgent

__all__ = [
    'FACT_EXTRACTOR_PROMPT',
    'FACT_VERIFICATION_PROMPT',
    'FactVerificationAgent'
] 