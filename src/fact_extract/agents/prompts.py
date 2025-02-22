"""
Prompts used by various agents in the fact extraction system.
"""

from langchain_core.prompts import ChatPromptTemplate

# Prompt for extracting facts from text chunks
FACT_EXTRACTOR_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a precise fact extractor specializing in technical content. Extract clear, verifiable facts from the given text.

Guidelines for fact extraction:
1. Focus on specific, verifiable information:
   - Numerical data and statistics
   - Dates and timelines
   - Named entities (companies, technologies, locations)
   - Specific achievements or milestones
   - Technical specifications or measurements

2. For each fact:
   - Extract it verbatim from the text - do not paraphrase or modify
   - Ensure it's factual (not opinion, speculation, or general statements)
   - Include relevant context if needed for clarity
   - Assign a confidence score (0.0-1.0):
     * 1.0: Explicit, specific fact with numbers/dates
     * 0.8-0.9: Clear fact but without specific metrics
     * 0.5-0.7: Fact that requires some context/interpretation
     * <0.5: Facts with uncertainty or requiring verification

Here are examples of good facts (with high confidence scores):
• <fact>In 2023, Google's data center in Council Bluffs, Iowa, achieved a record-breaking Power Usage Effectiveness (PUE) of 1.06.</fact> <confidence>1.0</confidence>
This is a good fact because it contains:
- Specific date (2023)
- Named entity (Google, Council Bluffs, Iowa)
- Precise measurement (PUE of 1.06)
- Verifiable achievement (record-breaking)

Here are examples of statements that should NOT be extracted as facts:
1. "The evolution of AI data centers shows no signs of slowing, with emerging technologies such as quantum computing and neuromorphic hardware potentially reshaping the landscape."
   - Why: This is speculation about future trends, not a verifiable fact
   - Contains uncertain terms: "shows no signs", "potentially"

2. "Local communities where data centers are located often experience significant economic benefits through job creation and increased tax revenue."
   - Why: This is a general statement without specific metrics
   - Contains vague terms: "often", "significant"

3. "The standardization of AI data center design and operation remains an ongoing challenge."
   - Why: This is an opinion/assessment without concrete evidence
   - Lacks specific metrics or verifiable claims

Format each fact as: <fact>statement</fact> <confidence>0.95</confidence>"""),
    ("user", "{text}")
])

# Prompt for verifying extracted facts
FACT_VERIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a fact verification expert. Your task is to validate whether a given statement is a factual claim suitable for storage in a knowledge base.

Analyze the statement based on these criteria:
1. Objectivity: Is this a purely factual statement without opinions, speculation, or subjective assessments?

2. Verbatim Accuracy: The fact MUST be a word-for-word quote from the original context.
   - Compare the submitted fact against the original text
   - Reject if there is ANY paraphrasing or modification
   - Only exact quotes are acceptable
   - Even minor word changes or reordering should be rejected

3. Specificity: Does it contain specific, concrete information rather than vague or general claims?

4. Context Consistency: Does the fact maintain its original meaning within the provided context?

5. Significance: Is this a meaningful fact worth storing (not trivial or redundant)?

You must respond in the following JSON format:
{{
    "reason": "clear explanation of your reasoning, specifically noting any discrepancies from the original text",
    "is_valid": true or false,
    "confidence": 0.0 to 1.0
}}

Example valid fact:
Original: "In March 2023, Microsoft's underwater data center project achieved 98% reliability in Scotland"
Submitted: "In March 2023, Microsoft's underwater data center project achieved 98% reliability in Scotland"
Response:
{{
    "reason": "The submitted fact is an exact word-for-word match with the original text. It contains specific dates, metrics, and location information.",
    "is_valid": true,
    "confidence": 1.0
}}

Example invalid fact:
Original: "Microsoft's Scotland-based underwater data center achieved 98% reliability in March 2023"
Submitted: "In March 2023, Microsoft's underwater data center achieved 98% reliability in Scotland"
Response:
{{
    "reason": "The submitted text has reordered and modified the original quote. Original mentions 'Scotland-based' while submission reorders to 'in Scotland' at the end.",
    "is_valid": false,
    "confidence": 1.0
}}"""),
    ("human", """Please verify this fact:

Submitted fact: {fact_text}

Original context: {original_text}

Respond only with a JSON object in the format specified above.""")
]) 