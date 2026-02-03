from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# Load environment variables
# ============================================================
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
print(f"----> Loading environment variables from {REPO_ROOT / '.env'}")
load_dotenv(dotenv_path=REPO_ROOT / ".env")


import asyncio
from typing import Any, AsyncGenerator

import agents
import gradio as gr
from gradio.components.chatbot import ChatMessage
from langfuse import propagate_attributes

# ---- internal imports (same pattern as efficient_multiple_kbs.py) ----
from src.utils import (
    oai_agent_stream_to_gradio_messages,
    set_up_logging,
    setup_langfuse_tracer,
)
from src.utils.agent_session import get_or_create_session
from src.utils.client_manager import AsyncClientManager
from src.utils.gradio import COMMON_GRADIO_CONFIG
from src.utils.langfuse.shared_client import langfuse_client

# ---- chatbot agents & tools ----
from src.health_chatbot.health_agents.orchestrator import build_orchestrator_agent


# ============================================================
# Async Gradio entrypoint
# ============================================================

async def _main(
    query: str,
    history: list[ChatMessage],
    session_state: dict[str, Any],
) -> AsyncGenerator[list[ChatMessage], Any]:

    turn_messages: list[ChatMessage] = []

    # Maintain conversational session
    session = get_or_create_session(history, session_state)

    with (
        langfuse_client.start_as_current_observation(
            name="Clinical Data Insights Chatbot",
            as_type="agent",
            input=query,
        ) as obs,
        propagate_attributes(session_id=session.session_id),
    ):
        result_stream = agents.Runner.run_streamed(
            orchestrator_agent,
            input=query,
            session=session,
            max_turns=30,
        )
        

        async for event in result_stream.stream_events():
            turn_messages += oai_agent_stream_to_gradio_messages(event)
            if turn_messages:
                yield turn_messages
        
        # # code to turn off the message streaming and only yield final output in UI
        # async for event in result_stream.stream_events():
        #         # Only render final responses to the UI
        #         if event.type == "response.completed":
        #                     turn_messages += oai_agent_stream_to_gradio_messages(event)
        #                     yield turn_messages



        obs.update(output=result_stream.final_output)


# ============================================================
# App bootstrap
# ============================================================

if __name__ == "__main__":

    # ---- logging & tracing ----
    set_up_logging()
    setup_langfuse_tracer()

    # ---- initialize shared client manager ----
    client_manager = AsyncClientManager()

    # ---- Orchestrator agent ----
    orchestrator_agent = build_orchestrator_agent(client_manager)

    # ========================================================
    # Gradio UI (logos on both extremes)
    # ========================================================

    with gr.Blocks(title="Clinical Data Insights Chatbot") as demo:
        with gr.Row():
            with gr.Column(scale=1):
                gr.Image(
                    value="assets/Shoppers-Drug-Mart-Logo-Vector-Image.jpg",
                    show_label=False,
                    height=60,
                )

            with gr.Column(scale=3):
                gr.Markdown(
                    """
                    <div style="text-align: center;">
                        <h2>Clinical Data Insights Chatbot</h2>
                        <p style="margin-top: -10px;">
                            Query • Analyze • Visualize
                        </p>
                    </div>
                    """
                )

            with gr.Column(scale=1):
                gr.Image(
                    value="assets/loblaw logo.jpg",
                    show_label=False,
                    height=60,
                )

        # ---- Chat UI ----
        gr.ChatInterface(
            _main,
            **COMMON_GRADIO_CONFIG,
            examples=[
            ["How many records are in the table?"],
            ["Show the average age pf patients by sex"],
            ["Plot number of records by region"],
            ['How many records have A1C greater than 6.5']
        ],
        )

    try:
        demo.launch(share=True)
    finally:
        asyncio.run(client_manager.close())