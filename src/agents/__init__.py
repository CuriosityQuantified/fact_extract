"""
Agent-related modules for the fact extraction system.
"""

from agents.prompts import FACT_EXTRACTOR_PROMPT, FACT_VERIFICATION_PROMPT
from agents.verification import FactVerificationAgent

__all__ = [
    'FACT_EXTRACTOR_PROMPT',
    'FACT_VERIFICATION_PROMPT',
    'FactVerificationAgent'
] 