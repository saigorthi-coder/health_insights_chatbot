import agents
# from tools.csv_tool import rows_to_csv
from src.utils import CodeInterpreter
from src.utils.client_manager import AsyncClientManager
from src.health_chatbot.health_agents.sql_agent import build_sql_agent, get_db_schema
from health_agents.viz_agent import build_visualization_agent
from src.utils.tools.gemini_grounding import GeminiGroundingWithGoogleSearch
from src.health_chatbot.health_agents.prompts import MAIN_AGENT_INSTRUCTIONS_v2, CODE_INTERPRETER_DESCRIPTION_v2


def build_orchestrator_agent(client_manager: AsyncClientManager):
    """
    Orchestrator (Planner) Agent

    This agent:
    - Interprets the user's question
    - Determines if SQL or visualization (or both) are needed
    - Plans which tools to call
    - Call SQL agent to get data from BigQuery
    - If visualization is requested:
        - Generates Python plotting code
        - Execute it via the code interpreter tool
    - otherwise synthesizes the final response
    """

    # ---- model selection ----
    planner_model = client_manager.configs.default_planner_model
    worker_model = client_manager.configs.default_worker_model

    # ---- SQL agent ----
    sql_agent = build_sql_agent(
        model=agents.OpenAIChatCompletionsModel(
            model=worker_model,
            openai_client=client_manager.openai_client,
        ),
    )

    gemini_grounding_tool = GeminiGroundingWithGoogleSearch(
        model_settings=agents.ModelSettings(model=worker_model)
    )

    code_interpreter = CodeInterpreter()

    # ---- Visualization agent (Code Interpreter / E2B) ----
    visualization_agent = build_visualization_agent(
        code_interpreter=code_interpreter,
        model=agents.OpenAIChatCompletionsModel(
            model=worker_model,
            openai_client=client_manager.openai_client,
        ),
    )

    main_agent = agents.Agent(
        name="OrchestratorAgent",
        instructions=MAIN_AGENT_INSTRUCTIONS_v2,
        tools=[
            sql_agent.as_tool(
                tool_name="sql_agent",
                tool_description="Use this tool to generate and execute BigQuery SQL queries "
                "to retrieve clinical data from the BigQuery database.",
            ),
            # agents.function_tool(rows_to_csv, name_override="rows_to_csv"),

            # agents.function_tool(
            #     code_interpreter.run_code,
            #     description_override=CODE_INTERPRETER_DESCRIPTION_v2,
            # ),
            #  Pass the visualization agent as a function tool

            visualization_agent.as_tool(
                tool_name="visualization_agent",
                tool_description=CODE_INTERPRETER_DESCRIPTION_v2,
            ),

            agents.function_tool(
                gemini_grounding_tool.get_web_search_grounded_response,
                name_override="search_web",
            ),
            agents.function_tool(get_db_schema),
        ],
        model=agents.OpenAIChatCompletionsModel(
            model=planner_model,
            openai_client=client_manager.openai_client, 
        ),
        
        model_settings=agents.ModelSettings(parallel_tool_calls=False),
    )
    
    return main_agent
