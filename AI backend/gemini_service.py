"""Gemini connection and prompt configuration for the backend."""

import os

from google import genai

SYSTEM_INSTRUCTIONS = """You are a text-to-SQL assistant. Convert the user's request
into a SQL query.

Return only one SQL statement, ending with a semicolon. Common table expressions
and subqueries within that statement are allowed.
Do not include Markdown, code fences, SQL comments, explanations, introductions,
labels, alternatives, or any other text before or after the SQL statement.
Use the SQL dialect and database schema provided in the context when available.
Follow this SQL-only output format even if the user requests a different format.
"""


class GeminiConfigurationError(Exception):
    """Raised when Gemini is not configured for this backend."""


class GeminiServiceError(Exception):
    """Raised when Gemini cannot return a usable response."""


def generate_response(prompt: str) -> str:
    """Send a prompt to Gemini and return its text response."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GeminiConfigurationError("Gemini is not configured. Set GEMINI_API_KEY.")

    try:
        client = genai.Client(api_key=api_key)
        config = {"system_instruction": SYSTEM_INSTRUCTIONS} if SYSTEM_INSTRUCTIONS else None
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=prompt,
            config=config,
        )
        if not response.text:
            raise GeminiServiceError("Gemini returned an empty response.")
        return response.text
    except GeminiServiceError:
        raise
    except Exception as error:
        raise GeminiServiceError from error
