"""SQL Agent migrated to Google ADK.

Changes from OpenAI SDK version:
- agents.Agent → google.adk.agents.Agent (LlmAgent)
- agents.function_tool(fn) → just pass fn directly to tools=[]
- agents.ModelSettings → generate_content_config for model settings
- No more OpenAIChatCompletionsModel wrapper
"""

from google.adk.agents import LlmAgent

from src.health_chatbot_Google_ADK.health_agents.prompts_adk import SQL_AGENT_INSTRUCTIONS_ADK
from src.health_chatbot_Google_ADK.tools.bigquery_tool_adk import get_db_schema, run_bigquery_query


def build_sql_agent(model: str) -> LlmAgent:
    """Build the SQL worker agent using Google ADK.

    Parameters
    ----------
    model : str
        Gemini model name (e.g., "gemini-2.5-flash").

    Returns
    -------
    LlmAgent
        ADK Agent configured for SQL generation and execution.
    """
    sql_agent = LlmAgent(
        name="SQLAgent",
        model=model,
        description="Generates and executes BigQuery SQL queries to retrieve clinical data.",
        instruction=SQL_AGENT_INSTRUCTIONS_ADK,
        tools=[run_bigquery_query, get_db_schema],
    )

    return sql_agent
