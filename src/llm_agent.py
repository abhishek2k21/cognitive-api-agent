# src/llm_agent.py

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from src.tools import AgentDecision # Import the new Union type
import json

def get_cognitive_agent(api_spec: str, chat_history: str):
    """
    Initializes the main cognitive agent with the API spec and conversation history.
    """
    system_prompt = (
        "You are an expert AI assistant that translates user requests into structured actions. "
        "You have two possible actions: ask a question, or formulate an API call.\n\n"
        "1.  **Analyze the Conversation**: Review the user's latest request in the context of the recent chat history and the API specification provided below.\n"
        "2.  **Check for Completeness**: Does the user's request contain ALL the necessary information (e.g., all required fields for a JSON payload) to make a valid API call according to the spec?\n"
        "3.  **DECIDE YOUR ACTION**:\n"
        "    -   If the request is INCOMPLETE, you MUST respond with a `Question` object. Ask for the specific missing fields.\n"
        "    -   If the request is COMPLETE, you MUST respond with an `APIRequest` object.\n\n"
        "Never make up data for fields. Always ask if information is missing.\n\n"
        "--- RECENT CHAT HISTORY ---\n"
        f"{chat_history}\n\n"
        "--- API SPECIFICATION ---\n"
        f"{api_spec}\n"
        "--- END OF CONTEXT ---"
    )
    
    return Agent(
        model=OpenAIModel('gpt-4o'),
        system_prompt=system_prompt,
        result_type=AgentDecision # The agent must choose between an APIRequest or a Question
    )