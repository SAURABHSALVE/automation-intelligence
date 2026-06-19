"""Shared base for all OpenAI-powered analyzers."""
import json
import os
from pathlib import Path
from typing import Any, Dict

import openai

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

MODEL = "gpt-4o"
MAX_TOKENS = 8192

# Absolute path to project root (src/analyzers/base_analyzer.py -> src/analyzers -> src -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class BaseAnalyzer:
    def __init__(self, prompt_file: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY not set")
        self.client = openai.OpenAI(api_key=api_key)
        self.system_prompt = self._load_prompt(prompt_file)

    @staticmethod
    def _load_prompt(path: str) -> str:
        p = Path(path)
        if not p.is_absolute():
            p = PROJECT_ROOT / path
        if not p.exists():
            raise FileNotFoundError(f"Prompt file not found: {p}")
        return p.read_text(encoding="utf-8")

    @retry(max_attempts=3, delay=5.0, backoff=2.0, exceptions=(openai.APIError, openai.RateLimitError))
    def _call_openai(self, user_message: str) -> str:
        logger.info("Calling OpenAI %s (prompt length: %d chars)", MODEL, len(user_message))
        response = self.client.chat.completions.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content

    MAX_DATA_CHARS = 60_000  # GPT-4o supports 128k tokens; stay well under

    def _format_data_for_prompt(self, data: Dict[str, Any]) -> str:
        text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        if len(text) > self.MAX_DATA_CHARS:
            logger.warning("Data truncated from %d to %d chars for OpenAI", len(text), self.MAX_DATA_CHARS)
            text = text[: self.MAX_DATA_CHARS] + "\n... [data truncated]"
        return text

    def analyze(self, data: Dict[str, Any]) -> str:
        raise NotImplementedError
