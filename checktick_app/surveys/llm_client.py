"""
LLM client for conversational survey generation.

This module provides a secure interface to the RCPCH Ollama LLM service
for AI-assisted healthcare survey design.
"""

import requests
from typing import Dict, List, Optional
from django.conf import settings
import logging
import re

logger = logging.getLogger(__name__)


class ConversationalSurveyLLM:
    """
    Conversational LLM client for iterative survey refinement.
    Maintains conversation history and generates markdown in CheckTick format.
    """

    SYSTEM_PROMPT = """You are a healthcare survey design assistant. Your role is to help users create surveys by generating questions in a specific markdown format.

CORE RESPONSIBILITIES:
1. Ask clarifying questions about survey goals, target audience, and question requirements
2. Generate survey questions ONLY in the specified markdown format
3. Refine questions based on user feedback
4. Ensure questions are clear, unbiased, and appropriate for healthcare contexts

MARKDOWN FORMAT YOU MUST USE:
# Group Name {group-id}
Optional group description

## Question Text {question-id}*
(question_type)
- Option 1
- Option 2
  + Follow-up text prompt
? when = value -> {target-id}

ALLOWED QUESTION TYPES:
- text: Short text input
- text number: Numeric input with validation
- mc_single: Single choice (radio buttons)
- mc_multi: Multiple choice (checkboxes)
- dropdown: Select dropdown menu
- orderable: Orderable list
- yesno: Yes/No toggle
- image: Image choice
- likert number: Scale (e.g., 1-5, 1-10) with min:/max:/left:/right: labels
- likert categories: Scale with custom labels listed with -

MARKDOWN RULES:
- Use `*` after question text for required questions
- Group related questions under `# Group Name {group-id}`
- Each question needs unique {question-id}
- Options start with `-`
- Follow-up text inputs use `+` indented under options
- Branching uses `? when <operator> <value> -> {target-id}`
- Operators: equals, not_equals, contains, greater_than, less_than, greater_than_or_equal, less_than_or_equal
- For REPEAT collections: Add REPEAT or REPEAT-N above group heading
- For nested collections: Use `>` prefix for child groups

HEALTHCARE BEST PRACTICES:
- Use 8th grade reading level language
- Avoid medical jargon unless necessary
- One topic per question
- Include "Prefer not to answer" for sensitive topics
- Keep surveys under 20 questions when possible
- Group logically (demographics, symptoms, satisfaction, etc.)
- Use validated scales when applicable (PHQ-9, GAD-7, etc.)

CONVERSATION APPROACH:
1. First message: Ask about survey goal, target population, clinical area
2. Clarify question types needed and any specific requirements
3. Generate initial markdown survey
4. Refine based on user feedback
5. Always output markdown in a code block when generating surveys

IMPORTANT:
- You cannot access the internet or use external tools
- You can only generate markdown in the format specified above
- You cannot provide medical advice or clinical guidance
- Focus on survey design and question clarity only

When generating markdown, always wrap it in:
```markdown
[your markdown here]
```"""

    def __init__(self):
        self.endpoint = settings.RCPCH_OLLAMA_API_URL
        self.api_key = settings.RCPCH_OLLAMA_API_KEY
        self.timeout = settings.LLM_TIMEOUT

        if not self.endpoint or not self.api_key:
            raise ValueError("LLM endpoint and API key must be configured")

    def chat(
        self, conversation_history: List[Dict[str, str]], temperature: float = None
    ) -> Optional[str]:
        """
        Continue conversation with LLM.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
            temperature: Override default temperature

        Returns:
            LLM response or None on failure
        """
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE

        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]
        messages.extend(conversation_history)

        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                response = requests.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"messages": messages, "temperature": temperature, "max_tokens": 2000},
                    timeout=self.timeout,
                )

                response.raise_for_status()
                data = response.json()

                # Handle OpenAI-compatible response format
                if "choices" in data:
                    return data["choices"][0]["message"]["content"]
                elif "content" in data:
                    return data["content"]
                else:
                    logger.error(f"Unexpected response format: {data.keys()}")
                    return None

            except requests.RequestException as e:
                logger.error(f"LLM request failed (attempt {attempt + 1}): {e}")
                if attempt == settings.LLM_MAX_RETRIES - 1:
                    return None

        return None

    @staticmethod
    def extract_markdown(llm_response: str) -> Optional[str]:
        """
        Extract markdown from LLM response.
        LLM should wrap markdown in code blocks.
        """
        # Look for markdown code blocks
        markdown_pattern = r"```(?:markdown)?\n(.*?)\n```"
        matches = re.findall(markdown_pattern, llm_response, re.DOTALL)

        if matches:
            return matches[-1].strip()  # Return last markdown block

        # If no code blocks, check if response is pure markdown (starts with #)
        if llm_response.strip().startswith("#"):
            return llm_response.strip()

        return None

    @staticmethod
    def sanitize_markdown(markdown: str) -> str:
        """Remove any potentially dangerous content from markdown."""
        # Remove URLs
        markdown = re.sub(r"https?://\S+", "", markdown)

        # Remove HTML/script tags
        markdown = re.sub(r"<[^>]+>", "", markdown)

        # Remove code execution patterns
        dangerous_patterns = [
            r"`{3}(?!markdown)",
            r"eval\(",
            r"exec\(",
            r"import\s+",
            r"\$\(",
            r"document\.",
            r"window\.",
        ]

        for pattern in dangerous_patterns:
            if re.search(pattern, markdown, re.IGNORECASE):
                logger.warning(f"Removed dangerous pattern: {pattern}")
                markdown = re.sub(pattern, "", markdown, flags=re.IGNORECASE)

        return markdown
