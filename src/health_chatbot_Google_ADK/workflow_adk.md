# Clinical Data Insights Chatbot — Google ADK Architecture

## Overview

This application is a multi-agent clinical data chatbot built on **Google Agent Development Kit (ADK)**. It allows non-technical users to query, analyze, and visualize clinical data stored in BigQuery through natural language. The system uses Gemini models via Vertex AI for reasoning, and coordinates multiple specialized agents to handle different aspects of each request.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                     Gradio UI (app_adk.py)              │
│                                                         │
│  User Query → Runner.run_async() → Stream Events → UI  │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              OrchestratorAgent (Root Agent)              │
│              Model: gemini-2.5-flash (planner)          │
│                                                         │
│  Interprets user intent, selects tools, synthesizes     │
│  final response. Does NOT write code — delegates.       │
│                                                         │
│  Tools:                                                 │
│  ┌────────────────┐  ┌──────────────────────────────┐   │
│  │  AgentTool:     │  │  AgentTool:                  │   │
│  │  SQLAgent       │  │  CodeExecutionAgent          │   │
│  └───────┬────────┘  └──────────────┬───────────────┘   │
│  ┌───────┴────────┐  ┌──────────────┴───────────────┐   │
│  │  Function Tool: │  │  Function Tool:              │   │
│  │  get_db_schema  │  │  search_web                  │   │
│  └────────────────┘  └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
          │                          │
          ▼                          ▼
┌──────────────────────┐   ┌─────────────────────────────┐
│      SQLAgent        │   │   CodeExecutionAgent        │
│  Model: gemini-2.5-  │   │   Model: gemini-2.5-flash   │
│         flash        │   │                             │
│                      │   │   Uses: BuiltInCodeExecutor │
│  Tools:              │   │   (Gemini native code exec) │
│  - run_bigquery_query│   │                             │
│  - get_db_schema     │   │   Generates AND executes    │
│                      │   │   Python code server-side   │
│  Queries BigQuery    │   │   (no external sandbox)     │
│  via personal creds  │   │                             │
└──────────┬───────────┘   └─────────────────────────────┘
           │
           ▼
┌──────────────────────┐
│   Google BigQuery    │
│   (Clinical Data)    │
│                      │
│   Table:             │
│   project-ad8e168b.. │
│   .Vector_AI_POC     │
│   .Health_Insurance_ │
│    Synthetic_PT_ID   │
└──────────────────────┘
```

---

## Agents in Detail

### 1. OrchestratorAgent (Root Agent)

**File:** `health_agents/orchestrator_adk.py`
**Model:** `gemini-2.5-flash` (configurable as `default_planner_model`)
**Role:** Planner and coordinator

The OrchestratorAgent is the entry point for all user queries. It receives the user's natural language question and decides which tools/agents to invoke and in what order. It never executes SQL or Python code directly — it delegates to specialized sub-agents.

**Decision logic:**
- **Data questions** → calls `SQLAgent` to query BigQuery
- **Visualization requests** → calls `SQLAgent` for data, then `CodeExecutionAgent` to generate and execute a chart
- **General knowledge questions** → calls `search_web` (Gemini grounding)
- **Schema discovery** → calls `get_db_schema` directly

**Key behaviors:**
- Always checks the database schema first via `get_db_schema` to understand what data is available
- Prefers SQL-side aggregation to minimize data transfer
- For visualizations: passes the data AND a plain English description to `CodeExecutionAgent` (does NOT write Python itself)
- Summarizes results in user-friendly language with cohort definitions, timeframes, and sample sizes
- Enforces safety policies: no DDL/DML, no revealing internal reasoning

### 2. SQLAgent (Sub-Agent)

**File:** `health_agents/sql_agent_adk.py`
**Model:** `gemini-2.5-flash` (configurable as `default_worker_model`)
**Role:** BigQuery SQL generation and execution

The SQLAgent translates natural language data requests into safe, efficient BigQuery SQL queries. It is exposed to the OrchestratorAgent as an `AgentTool`, meaning the orchestrator calls it like a tool but it operates as a full LLM agent with its own reasoning loop.

**Tools available to SQLAgent:**
| Tool | Purpose |
|------|---------|
| `run_bigquery_query(sql, max_rows)` | Executes a SQL query against BigQuery and returns structured results |
| `get_db_schema()` | Returns the table schema (column names and types), cached after first call |

**Key behaviors:**
- **Security:** READ-ONLY queries only. All write operations (INSERT, UPDATE, DELETE, etc.) are forbidden.
- **Scope:** Queries only the single table `project-ad8e168b-9904-43b7-b43.Vector_AI_POC.Health_Insurance_Synthetic_PT_ID`. No joins, no other tables.
- **Efficiency:** Prefers aggregated results, filters early, limits output to ≤ 500 rows.
- **Error handling:** Retries up to 3 times on SQL failure, correcting errors each attempt.
- **Output format:** Returns a structured JSON with `success`, `sql`, `row_count`, `rows`, `error_message`, and `notes`.

### 3. CodeExecutionAgent (Sub-Agent)

**File:** `health_agents/orchestrator_adk.py` (defined inline)
**Model:** `gemini-2.5-flash` (configurable as `default_worker_model`)
**Role:** Python code generation and execution for analysis/visualization

The CodeExecutionAgent uses Gemini's **BuiltInCodeExecutor** — a native capability where the model generates Python code AND executes it server-side within Google's infrastructure. This replaces the previous E2B sandbox approach.

**Key architectural difference from the old system:**
| Aspect | Old (E2B) | New (ADK BuiltInCodeExecutor) |
|--------|-----------|-------------------------------|
| Who writes code? | OrchestratorAgent writes Python code | CodeExecutionAgent writes its own code |
| Who executes code? | E2B cloud sandbox | Gemini's built-in server-side execution |
| How is it called? | Orchestrator sends code string as tool argument | Orchestrator describes the task in plain English |
| Execution environment | Isolated Docker container (E2B) | Google's managed code execution sandbox |
| State between calls | Fresh sandbox each call | Stateless (same behavior) |

**ADK constraint:** `BuiltInCodeExecutor` **cannot coexist with other tools** in the same agent. This is why it's wrapped in its own dedicated `LlmAgent` and exposed to the orchestrator via `AgentTool`. This is the documented workaround from the [ADK tool limitations guide](https://google.github.io/adk-docs/tools/limitations/#one-tool-one-agent).

**Capabilities:**
- Data processing with pandas, numpy
- Statistical computations
- Visualization with matplotlib, seaborn
- General Python computation

### 4. search_web (Function Tool)

**File:** `src/utils/tools/gemini_grounding.py` (shared utility, unchanged)
**Role:** Web search for general knowledge questions

This is a function tool (not a sub-agent) that calls Gemini with Google Search grounding enabled. It is used only when the user's question cannot be answered from the database — for example, general medical context questions where up-to-date information matters.

**How it works:**
1. Sends the query to a Gemini grounding proxy
2. Gemini automatically generates search queries and fetches results
3. Returns a synthesized response with inline citations

### 5. get_db_schema (Function Tool)

**File:** `tools/bigquery_tool_adk.py`
**Role:** Returns the BigQuery table schema

A simple function tool that queries `INFORMATION_SCHEMA.COLUMNS` to retrieve column names and data types. The result is **cached in memory** after the first call, so subsequent invocations are instant.

---

## Request Workflows

### Non-Visualization Query

```
User: "How many patients have diabetes?"
  │
  ▼
OrchestratorAgent
  ├── 1. Calls get_db_schema → learns available columns
  ├── 2. Calls SQLAgent → "Count patients with diabetes"
  │       └── SQLAgent calls run_bigquery_query(SQL)
  │           └── Returns: {success: true, rows: [{count: 1234}]}
  └── 3. Synthesizes response:
         "There are 1,234 patients with diabetes in the dataset (N=10,000 total)."
```

### Visualization Query

```
User: "Plot the distribution of patients by blood pressure category"
  │
  ▼
OrchestratorAgent
  ├── 1. Calls get_db_schema → learns available columns
  ├── 2. Calls SQLAgent → "Get patient counts by blood pressure category"
  │       └── Returns: {rows: [{category: "Normal", count: 3000}, ...]}
  ├── 3. Calls CodeExecutionAgent →
  │       "Here is the data: [...]. Create a bar chart showing
  │        patient distribution by blood pressure category."
  │       └── CodeExecutionAgent:
  │           a. Writes matplotlib code
  │           b. Executes via BuiltInCodeExecutor
  │           c. Returns chart output
  └── 4. Synthesizes response:
         "The majority of patients (40%) fall in the Normal category,
          followed by Elevated (25%)..."
```

### General Knowledge Query

```
User: "What are the latest guidelines for A1C management?"
  │
  ▼
OrchestratorAgent
  ├── 1. Calls get_db_schema → determines this isn't in the DB
  ├── 2. Calls search_web → "Latest A1C management guidelines"
  │       └── Returns: grounded response with citations
  └── 3. Passes through the response with source attributions
```

---

## File Structure

```
src/health_chatbot_sai/
├── app_adk.py                          # Gradio UI entry point
│                                        # - Initializes Runner + SessionService
│                                        # - Converts ADK events → Gradio messages
│                                        # - Handles session lifecycle per conversation
│
├── config_adk.py                       # Configuration (Pydantic settings)
│                                        # - BigQuery constants (project, dataset, table)
│                                        # - Model selection (planner/worker)
│                                        # - Vertex AI settings (ADC auth)
│                                        # - LangFuse + web search settings
│
├── health_agents/
│   ├── orchestrator_adk.py             # Builds the multi-agent hierarchy
│   │                                    # - Creates SQLAgent, CodeExecutionAgent
│   │                                    # - Wraps sub-agents with AgentTool
│   │                                    # - Assembles OrchestratorAgent with all tools
│   │
│   ├── sql_agent_adk.py                # SQL worker agent definition
│   │                                    # - LlmAgent with BQ tools
│   │
│   └── prompts_adk.py                  # All system instructions
│                                        # - MAIN_AGENT_INSTRUCTIONS_ADK (orchestrator)
│                                        # - SQL_AGENT_INSTRUCTIONS_ADK (sql worker)
│                                        # - CODE_EXECUTION_AGENT_INSTRUCTIONS (code exec)
│
└── tools/
    └── bigquery_tool_adk.py            # BigQuery execution functions
                                         # - run_bigquery_query(): executes SQL
                                         # - get_db_schema(): cached schema retrieval
                                         # - Uses personal credentials (gcloud auth)
```

---

## Authentication

| Service | Auth Method | Setup Command |
|---------|------------|---------------|
| Gemini / Vertex AI | Default Service Account (ADC) | Pre-configured, no action needed |
| BigQuery | Personal user credentials | `gcloud auth application-default login` |
| LangFuse | API keys in `.env` | Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` |
| Web Search | API key in `.env` | Set `WEB_SEARCH_BASE_URL` and `WEB_SEARCH_API_KEY` |

The BigQuery client explicitly loads credentials from `%APPDATA%/gcloud/application_default_credentials.json` to use personal email credentials, separate from the service account used for Gemini.

---

## Key Design Decisions

1. **AgentTool pattern:** ADK's `BuiltInCodeExecutor` cannot share an agent with other tools. The workaround is wrapping code execution in its own `LlmAgent` and exposing it as an `AgentTool` to the orchestrator. This is the [documented approach](https://google.github.io/adk-docs/tools/limitations/#one-tool-one-agent).

2. **Orchestrator delegates code writing:** Unlike the old E2B approach where the orchestrator generated Python code and sent it to a sandbox, the new CodeExecutionAgent generates its own code. The orchestrator only describes what it needs in plain English + provides data.

3. **Separate credentials for BQ:** The default ADC (service account) is used for Gemini. BigQuery uses personal credentials loaded from the gcloud credential file to ensure data access is tied to the user's identity.

4. **InMemorySessionService:** Sessions are stored in memory for development. Each Gradio conversation gets a unique session ID, enabling multi-turn context within a chat.

---

## Running the Application

```bash
# 1. Ensure gcloud auth is set up for BigQuery
gcloud auth application-default login

# 2. Run from the repo root
cd C:\Users\sgorthi\Gitprojects\health-insights-chat-bot
python -m src.health_chatbot_sai.app_adk
```
