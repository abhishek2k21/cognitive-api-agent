from dataclasses import dataclass
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext, Tool
from typing import Optional, List, Literal, Dict
import json # Import the json library
import os

from database import DatabaseConn
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

from pydantic_ai.models.openai import OpenAIModel

# --- Pydantic Schemas for Structured Responses and Tool Inputs ---

class AgentResponse(BaseModel):
    response_type: Literal["dml_success", "ddl_generated", "error"]
    message: str
    sql_query: Optional[str] = None
    note: Optional[dict] = None
    titles: Optional[List[str]] = None

class Column(BaseModel):
    name: str = Field(..., description="The name of the column.")
    type: str = Field(..., description="The SQL data type of the column.")

class DDLIntent(BaseModel):
    action: Literal["create_table", "add_column"]
    table_name: str
    columns: Optional[List[Column]] = None
    target_column: Optional[Column] = None

# --- Dependencies for Tools ---
@dataclass
class Dependencies:
    db: DatabaseConn

# --- TOOLS ---
# All functions decorated with @Tool are available for the agent to use.

@Tool
def generate_ddl_sql(intent: DDLIntent) -> AgentResponse:
    """Generates a DDL SQL query for creating or altering tables."""
    try:
        if intent.action == "create_table":
            if not intent.columns:
                raise ValueError("Columns are required to create a table.")
            cols_str = ", ".join([f'"{c.name}" {c.type}' for c in intent.columns])
            sql = f"CREATE TABLE \"{intent.table_name}\" ({cols_str});"
        elif intent.action == "add_column":
            if not intent.target_column:
                raise ValueError("A target column is required to add a column.")
            col = intent.target_column
            sql = f"ALTER TABLE \"{intent.table_name}\" ADD COLUMN \"{col.name}\" {col.type};"
        else:
            raise ValueError(f"Unknown DDL action: {intent.action}")

        return AgentResponse(
            response_type="ddl_generated",
            message="SQL query generated successfully. Please review and confirm execution.",
            sql_query=sql
        )
    except ValueError as e:
        return AgentResponse(response_type="error", message=str(e))

@Tool
async def create_note_tool(ctx: RunContext[Dependencies], title: str, text: str) -> AgentResponse:
    """Creates a new note with a given title and text."""
    success = await ctx.deps.db.add_note(title, text)
    msg = f"Note '{title}' created successfully." if success else f"Failed: Note '{title}' may already exist."
    return AgentResponse(response_type="dml_success", message=msg)

@Tool
async def retrieve_note_tool(ctx: RunContext[Dependencies], title: str) -> AgentResponse:
    """Retrieves a single note by its title."""
    note = await ctx.deps.db.get_note_by_title(title)
    msg = f"Retrieved note '{title}'." if note else f"Note '{title}' not found."
    return AgentResponse(response_type="dml_success", message=msg, note=note)

@Tool
async def list_notes_tool(ctx: RunContext[Dependencies]) -> AgentResponse:
    """Lists the titles of all available notes."""
    titles = await ctx.deps.db.list_all_titles()
    return AgentResponse(response_type="dml_success", message="Retrieved all note titles.", titles=titles)

@Tool
async def update_note_tool(ctx: RunContext[Dependencies], title: str, new_text: str) -> AgentResponse:
    """Updates the text of an existing note."""
    success = await ctx.deps.db.update_note(title, new_text)
    msg = f"Note '{title}' updated successfully." if success else f"Failed to update note '{title}' (not found?)."
    return AgentResponse(response_type="dml_success", message=msg)

@Tool
async def delete_note_tool(ctx: RunContext[Dependencies], title: str) -> AgentResponse:
    """Deletes a note by its title."""
    success = await ctx.deps.db.delete_note(title)
    msg = f"Note '{title}' deleted successfully." if success else f"Failed to delete note '{title}' (not found?)."
    return AgentResponse(response_type="dml_success", message=msg)

@Tool
async def search_notes_tool(ctx: RunContext[Dependencies], search_term: str) -> AgentResponse:
    """Searches for notes containing a specific term in their content."""
    titles = await ctx.deps.db.search_notes(search_term)
    msg = f"Found {len(titles)} notes containing '{search_term}'."
    return AgentResponse(response_type="dml_success", message=msg, titles=titles)

# --- Main Agent Definition ---

main_agent = Agent(
    model=OpenAIModel('gpt-4o'),
    tools=[
        generate_ddl_sql,
        create_note_tool,
        retrieve_note_tool,
        list_notes_tool,
        update_note_tool,
        delete_note_tool,
        search_notes_tool,
    ],
    system_prompt=(
        "You are a tool-calling engine. Based on the user's input, you MUST call one of the available tools. "
        "DO NOT respond with conversational text. Your sole purpose is to translate user requests into tool calls. "
        "For table creation or modification, use `generate_ddl_sql`. "
        "For note management, use the appropriate note tool (`Notes_tool`, `delete_note_tool`, etc.)."
    )
)

# --- Handler and Executor Functions ---

async def ask_generate(query: str) -> AgentResponse:
    """The main entry point called by the UI. It runs the agent to get a response."""
    deps = Dependencies(db=DatabaseConn())
    try:
        run_result = await main_agent.run(query, deps=deps)
        agent_output = run_result.data

        # Ideal case: agent returns the Pydantic object directly.
        if isinstance(agent_output, AgentResponse):
            return agent_output

        # Add-on case: agent returns a JSON string.
        if isinstance(agent_output, str):
            try:
                # Attempt to parse the JSON string.
                parsed_json = json.loads(agent_output)
                # Validate the parsed dictionary against our Pydantic model.
                return AgentResponse(**parsed_json)
            except (json.JSONDecodeError, TypeError) as e:
                # The string was not valid JSON.
                print(f"Agent returned a non-JSON string: {agent_output}. Error: {e}")
                return AgentResponse(
                    response_type="error",
                    message="The agent returned a response that could not be understood."
                )

        # Fallback for any other unexpected type.
        print(f"Unexpected agent output type: {type(agent_output)} | Content: {agent_output}")
        return AgentResponse(
            response_type="error",
            message="The agent returned an unexpected response. Please try rephrasing your command."
        )

    except Exception as e:
        print(f"Error during agent run: {e}")
        return AgentResponse(response_type="error", message=f"Sorry, an error occurred: {e}")

async def ask_execute(sql: str):
    """The secondary entry point to execute confirmed SQL."""
    deps = Dependencies(db=DatabaseConn())
    return await deps.db.execute_dynamic_ddl(sql)