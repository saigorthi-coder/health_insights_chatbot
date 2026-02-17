"""
Gradio entry point for Clinical Data Insights Chatbot (Google ADK).

Usage:
    python -m src.health_chatbot_Google_ADK.app_adk
"""

# ============================================================
# Load environment variables
# ============================================================

from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
print(f"----> Loading environment variables from {REPO_ROOT / '.env'}")
load_dotenv(dotenv_path=REPO_ROOT / ".env")

# ============================================================
# Imports
# ============================================================

import os
import uuid
import base64
from typing import Any, AsyncGenerator

import gradio as gr
from gradio.components.chatbot import ChatMessage
from langfuse import Langfuse, propagate_attributes

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types as genai_types

from src.health_chatbot_Google_ADK.config_adk import ADKConfigs
from src.health_chatbot_Google_ADK.health_agents.orchestrator_adk import (build_orchestrator_agent,)

# ============================================================
# Vertex AI Environment
# ============================================================

os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

# ============================================================
# Globals
# ============================================================

APP_NAME = "clinical_data_chatbot"

runner: Runner = None  # initialized in __main__
session_service: InMemorySessionService = None
langfuse_client: Langfuse | None = None

artifact_service = InMemoryArtifactService()
#(root_dir="./src/health_chatbot_Google_ADK/artifacts")

# ============================================================
# ADK Event → Gradio Conversion
# ============================================================


def adk_event_to_gradio_messages(event) -> list[ChatMessage]:
    """Convert ADK streaming event to Gradio ChatMessages (with artifact rendering)."""

    messages: list[ChatMessage] = []

    if not event.content or not event.content.parts:
        return messages

    author = event.author or "Agent"

    for part in event.content.parts:

        # ----------------------------------------------------
        # TEXT OUTPUT
        # ----------------------------------------------------
        if getattr(part, "text", None):
            is_final = author == "OrchestratorAgent"

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=part.text,
                    metadata={"title": f"[{author}]", "status": "done"}
                    if not is_final
                    else {},
                )
            )

        # ----------------------------------------------------
        # TOOL CALL
        # ----------------------------------------------------
        if getattr(part, "function_call", None):
            fc = part.function_call
            args_str = str(fc.args) if fc.args else ""

            if len(args_str) > 800:
                args_str = args_str[:800] + "..."

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"```json\n{args_str}\n```",
                    metadata={"title": f"Tool: {fc.name}"},
                )
            )

        # ----------------------------------------------------
        # TOOL RESPONSE
        # ----------------------------------------------------
        if getattr(part, "function_response", None):
            fr = part.function_response
            response_text = str(fr.response) if fr.response else ""

            if len(response_text) > 1200:
                response_text = response_text[:1200] + "..."

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"```\n{response_text}\n```",
                    metadata={"title": "Tool output", "status": "done"},
                )
            )

        # ----------------------------------------------------
        # GENERATED PYTHON CODE
        # ----------------------------------------------------
        if getattr(part, "executable_code", None):
            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"```python\n{part.executable_code.code}\n```",
                    metadata={"title": f"[{author}] Generated Code"},
                )
            )

        # ----------------------------------------------------
        # CODE EXECUTION OUTPUT
        # ----------------------------------------------------
        if getattr(part, "code_execution_result", None):
            output = part.code_execution_result.output or ""

            messages.append(
                ChatMessage(
                    role="assistant",
                    content=f"```\n{output}\n```",
                    metadata={"title": "Code Output", "status": "done"},
                )
            )

        # ----------------------------------------------------
        # ARTIFACT (PLOTS / FILES)
        # ----------------------------------------------------
        if getattr(part, "artifact", None):
            artifact = part.artifact

            # Image (matplotlib plot, etc.)
            if artifact.mime_type.startswith("image/"):
                img_base64 = base64.b64encode(artifact.data).decode("utf-8")

                img_html = f"""
                <div style="margin-top:10px;">
                    <img src="data:{artifact.mime_type};base64,{img_base64}"
                         style="max-width:100%; border-radius:8px;" />
                </div>
                """

                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=img_html,
                        metadata={"title": "Generated Plot"},
                    )
                )

            # Other file artifact
            else:
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=f"Artifact saved: {artifact.name} ({artifact.mime_type})",
                        metadata={"title": "Artifact"},
                    )
                )

    return messages


# ============================================================
# Async Gradio Entrypoint
# ============================================================


async def _main(query: str,history: list[ChatMessage],session_state: dict[str, Any] | None = None,) -> AsyncGenerator[list[ChatMessage], Any]:

    if session_state is None:
        session_state = {}

    turn_messages: list[ChatMessage] = []

    # --------------------------------------------------------
    # Create / Reuse ADK Session
    # --------------------------------------------------------
    if "adk_session_id" not in session_state:
        session_id = str(uuid.uuid4())

        await session_service.create_session(
            app_name=APP_NAME,
            user_id="gradio_user",
            session_id=session_id,
        )

        session_state["adk_session_id"] = session_id
    else:
        session_id = session_state["adk_session_id"]

    # --------------------------------------------------------
    # Create Gemini Content
    # --------------------------------------------------------
    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=query)],
    )

    # --------------------------------------------------------
    # Stream Agent
    # --------------------------------------------------------
    if langfuse_client is None:
        async for event in runner.run_async(
            user_id="gradio_user",
            session_id=session_id,
            new_message=user_message,
        ):
            new_messages = adk_event_to_gradio_messages(event)
            turn_messages.extend(new_messages)

            if turn_messages:
                yield turn_messages

        return

    with (
        langfuse_client.start_as_current_observation(
            name="Clinical Data Insights Chatbot (ADK)",
            as_type="agent",
            input=query,
        ) as obs,
        propagate_attributes(session_id=session_id),
    ):
        async for event in runner.run_async(
            user_id="gradio_user",
            session_id=session_id,
            new_message=user_message,
        ):
            new_messages = adk_event_to_gradio_messages(event)
            turn_messages.extend(new_messages)

            if turn_messages:
                yield turn_messages

        final_output = ""
        for msg in reversed(turn_messages):
            if msg.role == "assistant" and isinstance(msg.content, str):
                final_output = msg.content
                break
        obs.update(output=final_output)


# ============================================================
# Application Bootstrap
# ============================================================

if __name__ == "__main__":

    # ---- Configuration ----
    configs = ADKConfigs()
    if configs.langfuse_public_key and configs.langfuse_secret_key:
        langfuse_client = Langfuse(
            public_key=configs.langfuse_public_key,
            secret_key=configs.langfuse_secret_key,
            host=configs.langfuse_host,
        )

    # ---- Build Orchestrator ----
    orchestrator = build_orchestrator_agent(configs)

    # ---- Session + Runner ----
    session_service = InMemorySessionService()

    runner = Runner(
        agent=orchestrator,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service,
    )

    # ========================================================
    # Gradio UI
    # ========================================================

    with gr.Blocks(title="Clinical Data Insights Chatbot (ADK)") as demo:
        gr.Markdown(
            """
            <div style="text-align: center;">
                <h1>Clinical Data Insights Chatbot</h1>
                <h3 style="margin-top: -10px;">
                    Google ADK | Query | Analyze | Visualize
                </h3>
            </div>
            """
        )

        gr.ChatInterface(
            _main,
            examples=[
                ["How many records are in the database?"],
                ["What patient features are there in your data?"],
                ["Show me a sample of two rows from your data."],
                ["How many patients have diabetes? broken down by gender."],
            ],
            analytics_enabled=True,
        )

    demo.launch(share=False)
