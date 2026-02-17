"""Migration tests for Google ADK.

Run with:
    python -m src.health_chatbot_sai.test_migration

Tests each component individually, then the full orchestrator.
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv


# ============================================================
# Setup
# ============================================================
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "project-ad8e168b-9904-43b7-b43")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")


# ============================================================
# Test helpers
# ============================================================

def print_test(name: str, status: str, detail: str = ""):
    icon = "PASS" if status == "pass" else "FAIL"
    print(f"  [{icon}] {name}")
    if detail:
        print(f"         {detail}")


async def run_agent_query(runner, query: str, user_id="test", session_id="test"):
    """Run a query through an agent and collect text responses."""
    from google.genai import types as genai_types

    message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=query)],
    )

    responses = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=message,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    responses.append(part.text)
    return responses


# ============================================================
# Test 1: Config loads
# ============================================================

def test_config():
    print("\n--- Test 1: Configuration ---")
    try:
        from src.health_chatbot_sai.config_adk import ADKConfigs
        configs = ADKConfigs()
        print_test("ADKConfigs loads", "pass",
                   f"planner={configs.default_planner_model}, worker={configs.default_worker_model}")
    except Exception as e:
        print_test("ADKConfigs loads", "fail", str(e))


# ============================================================
# Test 2: BigQuery schema tool
# ============================================================

def test_db_schema():
    print("\n--- Test 2: Database Schema ---")
    try:
        from src.health_chatbot_sai.tools.bigquery_tool import get_db_schema
        schema = get_db_schema()
        if isinstance(schema, list) and len(schema) > 0:
            print_test("get_db_schema", "pass",
                       f"Found {len(schema)} columns, first: {schema[0]}")
        else:
            print_test("get_db_schema", "fail", f"Unexpected result: {schema}")
    except Exception as e:
        print_test("get_db_schema", "fail", str(e))


# ============================================================
# Test 3: BigQuery query tool
# ============================================================

def test_bq_query():
    print("\n--- Test 3: BigQuery Query ---")
    try:
        from src.health_chatbot_sai.tools.bigquery_tool import run_bigquery_query
        from src.health_chatbot_sai.config_adk import FULL_TABLE_NAME

        result = run_bigquery_query(f"SELECT COUNT(*) as cnt FROM {FULL_TABLE_NAME}")
        if result["success"]:
            print_test("run_bigquery_query", "pass",
                       f"Row count query returned: {result['rows']}")
        else:
            print_test("run_bigquery_query", "fail", result["error_message"])
    except Exception as e:
        print_test("run_bigquery_query", "fail", str(e))


# ============================================================
# Test 4: SQL Agent (ADK)
# ============================================================

async def test_sql_agent():
    print("\n--- Test 4: SQL Agent (ADK) ---")
    try:
        from google.adk.runners import InMemoryRunner
        from src.health_chatbot_sai.health_agents.sql_agent_adk import build_sql_agent
        from src.health_chatbot_sai.config_adk import ADKConfigs

        configs = ADKConfigs()
        agent = build_sql_agent(model=configs.default_worker_model)
        runner = InMemoryRunner(agent=agent)

        responses = await run_agent_query(
            runner,
            "How many records are in the database? Use get_db_schema first.",
        )
        if responses:
            print_test("SQL Agent query", "pass",
                       f"Response: {responses[-1][:200]}...")
        else:
            print_test("SQL Agent query", "fail", "No response received")
    except Exception as e:
        print_test("SQL Agent query", "fail", str(e))
        import traceback
        traceback.print_exc()


# ============================================================
# Test 5: Code Execution Agent (ADK BuiltInCodeExecutor)
# ============================================================

async def test_code_execution():
    print("\n--- Test 5: Code Execution Agent ---")
    try:
        from google.adk.agents import Agent
        from google.adk.code_executors import BuiltInCodeExecutor
        from google.adk.runners import InMemoryRunner
        from src.health_chatbot_sai.config_adk import ADKConfigs

        configs = ADKConfigs()
        code_agent = Agent(
            name="TestCodeAgent",
            model=configs.default_worker_model,
            description="Test code execution agent",
            instruction="You execute Python code to answer questions.",
            code_executor=BuiltInCodeExecutor(),
        )
        runner = InMemoryRunner(agent=code_agent)

        responses = await run_agent_query(
            runner,
            "Calculate the sum of [1, 2, 3, 4, 5] using Python code.",
            session_id="test_code",
        )
        if responses:
            print_test("Code execution", "pass",
                       f"Response: {responses[-1][:200]}")
        else:
            print_test("Code execution", "fail", "No response received")
    except Exception as e:
        print_test("Code execution", "fail", str(e))
        import traceback
        traceback.print_exc()


# ============================================================
# Test 6: Full Orchestrator (ADK)
# ============================================================

async def test_orchestrator():
    print("\n--- Test 6: Full Orchestrator ---")
    try:
        from google.adk.runners import InMemoryRunner
        from src.health_chatbot_sai.config_adk import ADKConfigs
        from src.health_chatbot_sai.health_agents.orchestrator_adk import (
            build_orchestrator_agent,
        )

        configs = ADKConfigs()
        orchestrator = build_orchestrator_agent(configs)
        runner = InMemoryRunner(agent=orchestrator)

        responses = await run_agent_query(
            runner,
            "How many records are in the database?",
            session_id="test_orch",
        )
        if responses:
            print_test("Orchestrator query", "pass",
                       f"Response: {responses[-1][:200]}")
        else:
            print_test("Orchestrator query", "fail", "No response received")
    except Exception as e:
        print_test("Orchestrator query", "fail", str(e))
        import traceback
        traceback.print_exc()


# ============================================================
# Test 7: Session history (multi-turn)
# ============================================================

async def test_session_history():
    print("\n--- Test 7: Session History ---")
    try:
        from google.adk.runners import InMemoryRunner
        from src.health_chatbot_sai.config_adk import ADKConfigs
        from src.health_chatbot_sai.health_agents.orchestrator_adk import (
            build_orchestrator_agent,
        )

        configs = ADKConfigs()
        orchestrator = build_orchestrator_agent(configs)
        runner = InMemoryRunner(agent=orchestrator)

        # Turn 1
        r1 = await run_agent_query(
            runner,
            "What columns are in the database?",
            session_id="test_session",
        )
        # Turn 2 - references previous context
        r2 = await run_agent_query(
            runner,
            "How many of those columns are numeric types?",
            session_id="test_session",
        )

        if r1 and r2:
            print_test("Session history", "pass",
                       f"Turn 1: {len(r1)} responses, Turn 2: {len(r2)} responses")
        else:
            print_test("Session history", "fail",
                       f"Turn 1: {len(r1)} responses, Turn 2: {len(r2)} responses")
    except Exception as e:
        print_test("Session history", "fail", str(e))
        import traceback
        traceback.print_exc()


# ============================================================
# Run all tests
# ============================================================

async def main():
    print("=" * 60)
    print("  Google ADK Migration Tests")
    print("=" * 60)

    # Synchronous tests
    test_config()
    test_db_schema()
    test_bq_query()

    # Async tests
    await test_sql_agent()
    await test_code_execution()
    await test_orchestrator()
    await test_session_history()

    print("\n" + "=" * 60)
    print("  Tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
