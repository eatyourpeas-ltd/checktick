"""
LLM client for conversational survey generation.

This module provides a secure interface to the RCPCH Ollama LLM service
for AI-assisted healthcare survey design.
"""

import json
import logging
from pathlib import Path
import re
from typing import Dict, List, Optional

from django.conf import settings
import requests

logger = logging.getLogger(__name__)


def load_system_prompt_from_docs() -> str:
    """
    Load the system prompt from the AI survey generator documentation.

    This ensures transparency - the prompt shown to users is exactly what the LLM receives.
    The prompt is extracted from the section between SYSTEM_PROMPT_START and SYSTEM_PROMPT_END markers.

    Returns:
        System prompt string, or fallback prompt if docs file cannot be read
    """
    docs_path = Path(settings.BASE_DIR) / "docs" / "ai-survey-generator.md"
    return _load_prompt_from_docs(
        docs_path, "SYSTEM_PROMPT_START", "SYSTEM_PROMPT_END", _FALLBACK_SYSTEM_PROMPT
    )


def load_translation_prompt_from_docs(target_language_name: str = None, target_language_code: str = None) -> str:
    """
    Load the translation system prompt from the LLM security documentation.

    This ensures transparency - the prompt shown to users is exactly what the LLM receives.
    The prompt is extracted from the section between TRANSLATION_PROMPT_START and TRANSLATION_PROMPT_END markers.

    Template variables are defined in the document's frontmatter and will be replaced if provided.

    Args:
        target_language_name: Name of target language (e.g., "Arabic") for template substitution
        target_language_code: ISO code of target language (e.g., "ar") for template substitution

    Returns:
        Translation prompt string with variables substituted, or fallback prompt if docs file cannot be read
    """
    docs_path = Path(settings.BASE_DIR) / "docs" / "llm-security.md"
    prompt = _load_prompt_from_docs(
        docs_path,
        "TRANSLATION_PROMPT_START",
        "TRANSLATION_PROMPT_END",
        _FALLBACK_TRANSLATION_PROMPT,
    )

    # Substitute template variables if provided
    if target_language_name and target_language_code:
        prompt = prompt.replace("{target_language_name}", target_language_name)
        prompt = prompt.replace("{target_language_code}", target_language_code)

    return prompt


def _load_prompt_from_docs(
    docs_path: Path, start_marker: str, end_marker: str, fallback: str
) -> str:
    """
    Generic helper to load a prompt from documentation.

    Args:
        docs_path: Path to the documentation file
        start_marker: Start marker comment (e.g., 'SYSTEM_PROMPT_START')
        end_marker: End marker comment (e.g., 'SYSTEM_PROMPT_END')
        fallback: Fallback prompt if loading fails

    Returns:
        Prompt string from docs or fallback
    """
    start_comment = f"<!-- {start_marker} -->"
    end_comment = f"<!-- {end_marker} -->"

    try:
        if docs_path.exists():
            content = docs_path.read_text(encoding="utf-8")

            start_idx = content.find(start_comment)
            end_idx = content.find(end_comment)

            if start_idx != -1 and end_idx != -1:
                # Extract text between markers and clean up
                prompt = content[start_idx + len(start_comment) : end_idx].strip()

                # Remove markdown code fence if present
                if prompt.startswith("```"):
                    lines = prompt.split("\n")
                    # Remove first line (```text or similar) and last line (```)
                    if lines[-1].strip() == "```":
                        prompt = "\n".join(lines[1:-1])

                # Remove leading/trailing whitespace from each line while preserving structure
                lines = prompt.split("\n")
                cleaned_lines = [line.rstrip() for line in lines]
                prompt = "\n".join(cleaned_lines).strip()

                logger.info(
                    f"Successfully loaded prompt from documentation: {docs_path.name}"
                )
                return prompt
            else:
                logger.warning(
                    f"Prompt markers {start_marker}/{end_marker} not found in {docs_path.name}"
                )
        else:
            logger.warning(f"Documentation file not found: {docs_path}")

    except Exception as e:
        logger.error(f"Failed to load prompt from docs: {e}")

    # Fallback to inline prompt if docs unavailable
    logger.info("Using fallback inline prompt")
    return fallback


# Fallback prompt if documentation file cannot be loaded
_FALLBACK_SYSTEM_PROMPT = """You are a healthcare survey design assistant. Your role is to help users create surveys by generating questions in a specific markdown format.

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


# Fallback translation prompt if documentation file cannot be loaded
_FALLBACK_TRANSLATION_PROMPT = """You are a professional medical translator specializing in healthcare surveys and clinical questionnaires.

CRITICAL INSTRUCTIONS:
1. Translate the ENTIRE survey to {target_language_name} ({target_language_code}) maintaining medical accuracy
2. Preserve technical/medical terminology precision - do NOT guess or approximate medical terms
3. Maintain consistency across all questions and answers
4. Keep formal, professional clinical tone throughout
5. Preserve any placeholders like {{variable_name}}
6. Use context from the full survey to ensure accurate, consistent translations
7. If you encounter medical terms where accurate translation is uncertain, note this in the confidence field

⚠️ TRANSLATION OUTPUT RULES - CRITICAL:
- Return ONLY the translated text - NO markdown formatting (no #, *, **, etc.)
- NO explanations, reasoning, or notes in the translated fields
- NO language codes like (ar), (fr) in the translations
- Just pure, plain translated text in each field
- Remove ALL source language markdown before translating
- Example: "# About You" becomes "عنك" (NOT "# عنك" or "# عنك (ar)")

CONFIDENCE LEVELS:
- "high": All translations are medically accurate and appropriate
- "medium": Most translations accurate but some terms may need review
- "low": Significant uncertainty - professional medical translator should review

⚠️ JSON OUTPUT REQUIREMENTS - CRITICAL:
- Return ONLY valid, parseable JSON - no trailing commas
- No comments or explanations outside the JSON structure
- Use proper JSON escaping for quotes within strings (use \\" for quotes in text)
- Ensure all brackets and braces are properly closed
- No extra commas after the last item in arrays or objects
- Test your JSON is valid before returning

Return ONLY valid JSON in this EXACT structure (INCLUDE ALL SECTIONS):
{
  "confidence": "high|medium|low",
  "confidence_notes": "explanation of any uncertainties or terms needing review",
  "metadata": {
    "name": "translated survey name",
    "description": "translated survey description"
  },
  "question_groups": [
    {
      "name": "translated group name",
      "description": "translated group description",
      "questions": [
        {
          "text": "translated question text",
          "choices": ["choice 1", "choice 2"],
          "likert_categories": ["category 1", "category 2"],
          "likert_scale": {"left_label": "...", "right_label": "..."}
        }
      ]
    }
  ]
}

NOTE:
- ALWAYS include the 'metadata' section with translated name and description
- Only include 'choices' if the source question has multiple choice options
- Only include 'likert_categories' if the source has likert scale categories (list of labels)
- Only include 'likert_scale' if the source has number scale with left/right labels
- NO trailing commas after last items in arrays or objects

Context: This is for a clinical healthcare platform. Accuracy is CRITICAL for patient safety."""


class ConversationalSurveyLLM:
    """
    Conversational LLM client for iterative survey refinement.
    Maintains conversation history and generates markdown in CheckTick format.

    The system prompt is loaded from docs/ai-survey-generator.md to ensure
    transparency - what users see in documentation is exactly what the LLM receives.
    """

    def __init__(self):
        self.endpoint = settings.LLM_URL
        self.api_key = settings.LLM_API_KEY
        self.auth_type = settings.LLM_AUTH_TYPE
        self.timeout = settings.LLM_TIMEOUT
        self.system_prompt = load_system_prompt_from_docs()

        if not self.endpoint or not self.api_key:
            raise ValueError("LLM endpoint and API key must be configured")

    def chat(
        self,
        conversation_history: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Continue conversation with LLM.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Maximum tokens in response (default: 2000)

        Returns:
            LLM response or None on failure
        """
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE
        if max_tokens is None:
            max_tokens = 2000

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(conversation_history)

        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                # Support both Azure APIM and standard OpenAI authentication
                headers = {"Content-Type": "application/json"}
                if self.auth_type.lower() == "apim":
                    headers["Ocp-Apim-Subscription-Key"] = self.api_key
                else:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=self.timeout,
                )

                response.raise_for_status()
                data = response.json()

                # Handle OpenAI-compatible response format
                content = None
                if "choices" in data:
                    content = data["choices"][0]["message"]["content"]
                elif "content" in data:
                    content = data["content"]
                else:
                    logger.error(f"Unexpected response format: {data.keys()}")
                    return None

                # Strip markdown code fences if present
                if content:
                    content = content.strip()
                    # Remove ```markdown and ``` wrappers
                    if content.startswith("```markdown"):
                        content = content[len("```markdown") :].strip()
                    elif content.startswith("```"):
                        content = content[3:].strip()
                    if content.endswith("```"):
                        content = content[:-3].strip()

                return content

            except requests.RequestException as e:
                logger.error(f"LLM request failed (attempt {attempt + 1}): {e}")
                if attempt == settings.LLM_MAX_RETRIES - 1:
                    return None

        return None

    def chat_with_custom_system_prompt(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> Optional[str]:
        """
        Chat with LLM using a custom system prompt (for specialized tasks like translation).

        Args:
            system_prompt: Custom system prompt to use instead of default
            conversation_history: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Maximum tokens in response (default: 2000)

        Returns:
            LLM response or None on failure
        """
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE
        if max_tokens is None:
            max_tokens = 2000

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)

        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                # Support both Azure APIM and standard OpenAI authentication
                headers = {"Content-Type": "application/json"}
                if self.auth_type.lower() == "apim":
                    headers["Ocp-Apim-Subscription-Key"] = self.api_key
                else:
                    headers["Authorization"] = f"Bearer {self.api_key}"

                response = requests.post(
                    self.endpoint,
                    headers=headers,
                    json={
                        "model": settings.LLM_MODEL,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                    timeout=self.timeout,
                )

                response.raise_for_status()
                data = response.json()

                # Handle OpenAI-compatible response format
                content = None
                if "choices" in data:
                    content = data["choices"][0]["message"]["content"]
                elif "content" in data:
                    content = data["content"]
                else:
                    logger.error(f"Unexpected response format: {data.keys()}")
                    return None

                # Strip markdown code fences if present
                if content:
                    content = content.strip()
                    # Remove ```markdown and ``` wrappers
                    if content.startswith("```markdown"):
                        content = content[len("```markdown") :].strip()
                    elif content.startswith("```"):
                        content = content[3:].strip()
                    if content.endswith("```"):
                        content = content[:-3].strip()

                return content

            except requests.RequestException as e:
                logger.error(f"LLM request failed (attempt {attempt + 1}): {e}")
                if attempt == settings.LLM_MAX_RETRIES - 1:
                    return None

        return None

    def chat_stream(
        self, conversation_history: List[Dict[str, str]], temperature: float = None
    ):
        """
        Stream conversation with LLM, yielding chunks as they arrive.

        Args:
            conversation_history: List of message dicts with 'role' and 'content'
            temperature: Override default temperature

        Yields:
            Chunks of the LLM response as they arrive
        """
        if temperature is None:
            temperature = settings.LLM_TEMPERATURE

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(conversation_history)

        headers = {"Content-Type": "application/json"}
        if self.auth_type.lower() == "apim":
            headers["Ocp-Apim-Subscription-Key"] = self.api_key
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json={
                    "model": settings.LLM_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 2000,
                    "stream": True,
                },
                timeout=self.timeout,
                stream=True,
            )

            response.raise_for_status()

            # Process the streaming response - stream everything as-is
            for line in response.iter_lines():
                if not line:
                    continue

                line = line.decode("utf-8")

                # Skip SSE comments and empty lines
                if line.startswith(":") or not line.strip():
                    continue

                # Parse SSE data
                if line.startswith("data: "):
                    data_str = line[6:]

                    # Check for end of stream
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        if "choices" in data and len(data["choices"]) > 0:
                            delta = data["choices"][0].get("delta", {})
                            chunk = delta.get("content", "")

                            if chunk:
                                # Stream each character
                                for char in chunk:
                                    yield char

                    except json.JSONDecodeError:
                        continue

        except requests.RequestException as e:
            logger.error(f"LLM streaming request failed: {e}")
            yield ""

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
