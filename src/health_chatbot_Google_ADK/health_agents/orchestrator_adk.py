"""Orchestrator Agent migrated to Google ADK.

Architecture (AgentTool pattern for ADK's one-tool-per-agent constraint):

    OrchestratorAgent (root)
    ├── AgentTool(SQLAgent)              ← sub-agent with BQ tools
    ├── AgentTool(CodeExecutionAgent)    ← sub-agent with BuiltInCodeExecutor
    ├── search_web                       ← function tool (gemini grounding)
    └── get_db_schema                    ← function tool (cached schema)

BuiltInCodeExecutor cannot coexist with other tools in the same agent,
so it's wrapped in its own dedicated agent and exposed to the orchestrator
via AgentTool.
"""

from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.tools.agent_tool import AgentTool

from src.health_chatbot_Google_ADK.config_adk import ADKConfigs
from src.health_chatbot_Google_ADK.health_agents.prompts_adk import (
    CODE_EXECUTION_AGENT_INSTRUCTIONS,
    MAIN_AGENT_INSTRUCTIONS_ADK,
)
from src.health_chatbot_Google_ADK.health_agents.sql_agent_adk import build_sql_agent
from src.health_chatbot_Google_ADK.tools.bigquery_tool_adk import get_db_schema
from src.utils.tools.gemini_grounding import GeminiGroundingWithGoogleSearch


def build_orchestrator_agent(configs: ADKConfigs) -> LlmAgent:
    """Build the orchestrator agent using Google ADK.

    Parameters
    ----------
    configs : ADKConfigs
        Application configuration.

    Returns
    -------
    LlmAgent
        Root orchestrator agent with all sub-agents and tools.
    """
    planner_model = configs.default_planner_model
    worker_model = configs.default_worker_model

    # ---- SQL Agent (sub-agent) ----
    sql_agent = build_sql_agent(model=worker_model)

    # ---- Code Execution Agent (sub-agent with BuiltInCodeExecutor) ----
    code_execution_agent = LlmAgent(
        name="CodeExecutionAgent",
        model=worker_model,
        description=(
            "Executes Python code for data analysis and visualization. "
            "Give it data and a plain English description of what to compute or plot. "
            "It will generate and execute Python code, then return the results."
        ),
        instruction=CODE_EXECUTION_AGENT_INSTRUCTIONS,
        code_executor=BuiltInCodeExecutor(),
    )

    # ---- Gemini Grounding (web search) ----
    gemini_grounding_tool = GeminiGroundingWithGoogleSearch(
        base_url=configs.web_search_base_url,
        api_key=configs.web_search_api_key,
    )

    # ---- Orchestrator (root agent) ----
    orchestrator = LlmAgent(
        name="OrchestratorAgent",
        model=planner_model,
        description="Orchestrator agent for clinical data insights.",
        instruction=MAIN_AGENT_INSTRUCTIONS_ADK,
        tools=[
            AgentTool(agent=sql_agent),
            AgentTool(agent=code_execution_agent),
            gemini_grounding_tool.get_web_search_grounded_response,
            get_db_schema,
        ],
    )

    return orchestrator
