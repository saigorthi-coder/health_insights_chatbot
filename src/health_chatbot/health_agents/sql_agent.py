import agents
from src.health_chatbot.tools.bigquery_tool import run_bigquery_query, get_db_schema
from src.health_chatbot.health_agents.prompts import SQL_AGENT_INSTRUCTIONS_v2
from src.health_chatbot.config import FULL_TABLE_NAME, DB_MAX_SQL_RETRIES


# =========================
# Replace variables in the prompt
# =========================
SQL_AGENT_INSTRUCTIONS = SQL_AGENT_INSTRUCTIONS_v2.format(
    MAX_SQL_RETRIES=DB_MAX_SQL_RETRIES,
    FULL_TABLE_NAME=FULL_TABLE_NAME,
)


def build_sql_agent(model):
  """
  SQL Agent (Worker)

  Responsibilities:
  - Translate natural language questions into BigQuery SQL
  - Execute SQL via the provided tool
  - Retry SQL generation/execution up to MAX_SQL_RETRIES times on failures or errors 
  - Enforce a single, fully-qualified BigQuery table
  - Return structured results to the orchestrator
  """

  sql_agent = agents.Agent(
      name="SQLAgent", 
      instructions=SQL_AGENT_INSTRUCTIONS,
      tools=[
          agents.function_tool(run_bigquery_query), 
          agents.function_tool(get_db_schema)
      ],    
      model=model, 
      model_settings=agents.ModelSettings(parallel_tool_calls=False),
  )

  return sql_agent
