# src/tools.py

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal, Union

# --- Pydantic Schemas for Agent Output ---

class APIRequest(BaseModel):
    """The agent's decision to call a specific API endpoint."""
    endpoint: str = Field(..., description="The API endpoint to call, e.g., '/register/customer'.")
    method: Literal["GET", "POST", "PUT", "DELETE"] = Field(..., description="The HTTP method to use.")
    json_payload: Optional[Dict[str, Any]] = Field(None, description="The JSON payload for POST or PUT requests.")
    params: Optional[Dict[str, Any]] = Field(None, description="The URL query parameters for GET requests.")

class Question(BaseModel):
    """The agent's decision to ask the user a clarifying question."""
    question_to_user: str = Field(..., description="A clear, specific question to ask the user to get missing information.")

# The agent's final output must be one of these two types
AgentDecision = Union[APIRequest, Question]