# Orchestrator Workflow (`orchestrator.py`)

- Defines `build_orchestrator_agent(client_manager)` to construct the main planner/orchestrator agent.
- Accepts an `AsyncClientManager`, which supplies model configuration and OpenAI client access.

## High-Level Responsibilities

- Interprets the user question.
- Plans which tools should be used.
- Routes data requests to a SQL tool/agent.
- Supports code execution via a code interpreter tool.
- Supports web-grounded responses via a Gemini grounding search tool.
- Produces the final response through the orchestrator agent.

## Step-by-Step Construction Flow

- Reads model names from config:
  - `planner_model` from `client_manager.configs.default_planner_model`.
  - `worker_model` from `client_manager.configs.default_worker_model`.
- Builds a SQL worker agent (`sql_agent`) using:
  - `build_sql_agent(...)`.
  - `agents.OpenAIChatCompletionsModel` configured with the `worker_model` and shared OpenAI client.
- Initializes a Gemini grounding tool (`GeminiGroundingWithGoogleSearch`) with worker model settings.
- Initializes a `CodeInterpreter` instance for Python/code execution.
- Creates the main orchestrator `agents.Agent` named `OrchestratorAgent` with:
  - Instructions from `MAIN_AGENT_INSTRUCTIONS_v2`.
  - Planner model (`planner_model`) via `OpenAIChatCompletionsModel`.
  - `parallel_tool_calls=False` (tools are invoked serially, not in parallel).

## Tools Registered on the Orchestrator

- `sql_agent` (as tool name `sql_agent`):
  - Purpose: generate and run BigQuery SQL for clinical data retrieval.
- `code_interpreter.run_code` (function tool):
  - Purpose: execute code, with behavior described by `CODE_INTERPRETER_DESCRIPTION_v2`.
- `gemini_grounding_tool.get_web_search_grounded_response` (function tool name `search_web`):
  - Purpose: fetch web-grounded responses/search support.
- `get_db_schema` (function tool):
  - Purpose: expose database schema to help SQL generation.

## Output

- Returns the fully configured `main_agent` orchestrator instance.

## Notes from Current File

- Visualization-specific agent construction is present but commented out.
- CSV conversion utility wiring is also commented out.
- The active flow centers on SQL access, code execution, schema lookup, and web-grounded search.
