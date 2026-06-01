from dataclasses import dataclass, asdict
import json
from typing import List, Dict, Any, Optional, Type, TypeVar

@dataclass
class TriageState:
    url: str
    issue: dict  # Expected structure: {"title": str, "body": str, "comments": list[str]}
    repo_tree: List[str]
    classification: Optional[dict] = None
    located_files: Optional[dict] = None
    debug_plan: Optional[dict] = None
    critic_review: Optional[dict] = None
    resolved_classification: Optional[dict] = None
    resolved_debug_plan: Optional[dict] = None
    resolver_notes: Optional[str] = None
    draft_response: Optional[str] = None
    audit_accuracy: Optional[str] = None
    current_step: str = "initialized"
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the state to a Python dictionary for logging/debugging."""
        return asdict(self)

    def to_json(self) -> str:
        """Serializes the state to a structured JSON string for debug displays."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriageState":
        """Creates a TriageState instance from a dictionary."""
        return cls(**data)
