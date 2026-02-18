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
    debug: bool = False,  # <-- new flag
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

        # -------------------------------
        # STREAM INTERMEDIATE EVENTS
        # -------------------------------
        async for event in result_stream.stream_events():
            # pass debug flag here
            messages = oai_agent_stream_to_gradio_messages(event, debug=debug)
            if messages:
                turn_messages += messages
                yield turn_messages

        # -------------------------------
        # SEND FINAL ANSWER TO GRADIO
        # -------------------------------
        final_text = result_stream.final_output
        if final_text:
            yield [
                ChatMessage(
                    role="assistant",
                    content=final_text
                )
            ]

        # update Langfuse with final output
        obs.update(output=final_text)


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
    # Gradio UI
    # ========================================================

    with gr.Blocks(title="Clinical Data Insights Chatbot") as demo:
        with gr.Row():
            with gr.Column(scale=1, min_width=100):
                gr.Image(
                    value="assets/Shoppers-Drug-Mart-Logo-Vector-Image.jpg",
                    show_label=False,
                    container=False, 
                    height=100,
                )
            with gr.Column(scale=3):
                gr.Markdown(
                    """
                    <div style="text-align: center;">
                        <h1>Clinical Data Insights Chatbot</h1>
                        <h3 style="margin-top: -10px;">
                            Query • Analyze • Visualize
                        </h3>
                    </div>
                    """
                )
            with gr.Column(scale=1, min_width=100):
                gr.Image(
                    value="assets/loblaw logo.jpg",
                    show_label=False,
                    container=False, 
                    height=100,
                )

        # ---- Chat UI ----
        gr.ChatInterface(
            _main,
            **COMMON_GRADIO_CONFIG,
            examples=[
                ["How many records are in the database?"],
                ["What patient features are there in your data?"],
                ["Show me a sample of two raws in from your data."],
                ["Plot number of patients per month"],
                ["How many patients have diabetes? broken down by gender."],
                ["Plot the distribution of patients in different blood pressure categories."],
                # ["What's the relationship between BMI and A1C levels in our data?"],
            ],
            analytics_enabled=False,
        )

    try:
        demo.launch(share=True)
    finally:
        asyncio.run(client_manager.close())