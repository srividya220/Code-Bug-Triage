import json
import os
from typing import Any, Optional

from dotenv import load_dotenv

from state import TriageState
import prompts

try:
    from google import genai  # type: ignore
    from google.genai import types  # type: ignore
except Exception:  # pragma: no cover - allow tests and local import without SDK
    genai = None

    class _DummyGenerateContentConfig:
        def __init__(self, **kwargs: Any):
            self.__dict__.update(kwargs)

    class _DummyTypes:
        GenerateContentConfig = _DummyGenerateContentConfig

    types = _DummyTypes()


load_dotenv()


class TriageAgent:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        """Initialize the Gemini client or a safe fallback when the SDK is unavailable."""
        resolved_api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not resolved_api_key:
            raise ValueError(
                "Gemini API key is missing. Please set GEMINI_API_KEY in your environment, ",
            )

        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        if genai is not None:
            self.client = genai.Client(api_key=resolved_api_key)
        else:
            class _MissingGenAIClient:
                class _MissingModels:
                    @staticmethod
                    def generate_content(*args: Any, **kwargs: Any):
                        raise ModuleNotFoundError(
                            "Gemini SDK is not installed. Install requirements.txt to run the agent."
                        )

                def __init__(self):
                    self.models = self._MissingModels()

            self.client = _MissingGenAIClient()

    @staticmethod
    def _parse_response_json(response: Any) -> dict:
        """Parse a Gemini response into JSON, handling optional markdown fences."""
        raw_text = getattr(response, "text", "") or ""
        cleaned = raw_text.strip()

        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[-1]

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return json.loads(cleaned[start_idx:end_idx + 1])
            raise

    @staticmethod
    def _format_comments(state: TriageState) -> str:
        comments = state.issue.get("comments", []) or []
        if not comments:
            return "(No comments on this issue)"
        return "\n".join(f"- {comment}" for comment in comments)

    def classify(self, state: TriageState) -> TriageState:
        state.current_step = "classifying"
        prompt = prompts.CLASSIFY_PROMPT.format(
            title=state.issue.get("title", ""),
            body=state.issue.get("body", ""),
            comments=self._format_comments(state),
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompts.ClassificationSchema,
                    temperature=0.1,
                ),
            )
            state.classification = self._parse_response_json(response)
        except Exception as exc:
            state.error = f"Classification step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def locate(self, state: TriageState) -> TriageState:
        state.current_step = "locating"
        repo_tree_str = "\n".join(state.repo_tree) if state.repo_tree else "(No repository files available)"
        prompt = prompts.LOCATE_PROMPT.format(
            title=state.issue.get("title", ""),
            body=state.issue.get("body", ""),
            comments=self._format_comments(state),
            repo_tree=repo_tree_str,
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompts.LocationSchema,
                    temperature=0.1,
                ),
            )
            state.located_files = self._parse_response_json(response)
        except Exception as exc:
            state.error = f"Location step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def suggest(self, state: TriageState) -> TriageState:
        state.current_step = "suggesting"
        prompt = prompts.SUGGEST_PROMPT.format(
            title=state.issue.get("title", ""),
            body=state.issue.get("body", ""),
            comments=self._format_comments(state),
            located_files=json.dumps(state.located_files or {}, indent=2),
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompts.SuggestionSchema,
                    temperature=0.2,
                ),
            )
            state.debug_plan = self._parse_response_json(response)
        except Exception as exc:
            state.error = f"Suggestion step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def respond(self, state: TriageState) -> TriageState:
        state.current_step = "responding"
        classification = state.classification or {}
        prompt = prompts.RESPOND_PROMPT.format(
            title=state.issue.get("title", ""),
            body=state.issue.get("body", ""),
            comments=self._format_comments(state),
            category=classification.get("category", "Unclassified"),
            severity=classification.get("severity", "Unknown"),
            affected_layer=classification.get("affected_layer", "Unknown"),
            located_files=json.dumps(state.located_files or {}, indent=2),
            debug_plan=json.dumps(state.debug_plan or {}, indent=2),
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.4),
            )
            state.draft_response = getattr(response, "text", "")
            state.current_step = "completed"
        except Exception as exc:
            state.error = f"Response draft step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def critique(self, state: TriageState) -> TriageState:
        state.current_step = "critic_review"
        prompt = prompts.CRITIC_PROMPT.format(
            classification=json.dumps(state.classification or {}, indent=2),
            located_files=json.dumps(state.located_files or {}, indent=2),
            debug_plan=json.dumps(state.debug_plan or {}, indent=2),
            repo_tree="\n".join(state.repo_tree) if state.repo_tree else "(No repository files available)",
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompts.CriticSchema,
                    temperature=0.2,
                ),
            )
            state.critic_review = self._parse_response_json(response)
        except Exception as exc:
            state.error = f"Critic review step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def resolve(self, state: TriageState) -> TriageState:
        state.current_step = "resolver_review"
        prompt = prompts.RESOLVE_PROMPT.format(
            classification=json.dumps(state.classification or {}, indent=2),
            located_files=json.dumps(state.located_files or {}, indent=2),
            debug_plan=json.dumps(state.debug_plan or {}, indent=2),
            critic_review=json.dumps(state.critic_review or {}, indent=2),
            repo_tree="\n".join(state.repo_tree) if state.repo_tree else "(No repository files available)",
        )
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=prompts.ResolverSchema,
                    temperature=0.2,
                ),
            )
            resolved = self._parse_response_json(response)
            state.resolved_classification = resolved.get("final_classification")
            state.resolved_debug_plan = resolved.get("final_debug_plan")
            state.resolver_notes = resolved.get("resolution_notes")
        except Exception as exc:
            state.error = f"Resolver review step failed: {exc}"
            state.current_step = "failed"
            raise
        return state

    def run_all(self, state: TriageState) -> TriageState:
        state = self.classify(state)
        state = self.locate(state)
        state = self.suggest(state)
        state = self.critique(state)
        state = self.resolve(state)
        state = self.respond(state)
        return state
