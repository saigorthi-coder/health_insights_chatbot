import agents
from tools.bigquery_tool import run_bigquery_query
from src.health_chatbot.health_agents.prompts import SQL_AGENT_INSTRUCTIONS_v2

# =========================
# HARD-CODED CONFIG
# =========================
MAX_SQL_RETRIES = 3

# Purposefully Hardcoded the Table Name for POC
BQ_PROJECT = "project-ad8e168b-9904-43b7-b43"
BQ_DATASET = "Vector_AI_POC"
BQ_TABLE = "Health_Insurance_Synthetic"

FULL_TABLE_NAME = f"`{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`"

# =========================
# Replace variables in the prompt
# =========================
SQL_AGENT_INSTRUCTIONS = SQL_AGENT_INSTRUCTIONS_v2.format(
    MAX_SQL_RETRIES=MAX_SQL_RETRIES,
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
          agents.function_tool(run_bigquery_query, name_override="run_bigquery_query")
      ],    
      model=model, 
      model_settings=agents.ModelSettings(parallel_tool_calls=False),
  )

  return sql_agent
