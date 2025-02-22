"""
Agent-related modules for the fact extraction system.
"""

from .prompts import FACT_EXTRACTOR_PROMPT, FACT_VERIFICATION_PROMPT
from .verification import FactVerificationAgent

__all__ = [
    'FACT_EXTRACTOR_PROMPT',
    'FACT_VERIFICATION_PROMPT',
    'FactVerificationAgent'
] 