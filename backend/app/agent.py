# agent.py
# LLM logic using AWS Bedrock Converse API (boto3).
# Drop-in replacement for the Anthropic SDK version —
# same AgentAction / AgentResponse types, same public interface.

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import boto3
import httpx
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from .models import AgentAction, AgentResponse


# ─────────────────────────────────────────────────────────────────────────────
# Bedrock client
# ─────────────────────────────────────────────────────────────────────────────
# Auth: set AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_DEFAULT_REGION
# in your .env, OR attach an IAM role to the instance (preferred in prod).
#
# Model ID: cross-region inference profile recommended for hackathon resilience.
# Verify available IDs in your account:
#   aws bedrock list-foundation-models --region us-east-1
#
# Claude Sonnet 4 (fast + capable — good default for demos):
MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-sonnet-4-20250514-v1:0",
)

def _make_bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=60,
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Tool schema  — Bedrock Converse format
# ─────────────────────────────────────────────────────────────────────────────
# Key difference from Anthropic SDK:
#   Anthropic:  {"name": ..., "description": ..., "input_schema": {...}}
#   Bedrock:    {"toolSpec": {"name": ..., "description": ...,
#                             "inputSchema": {"json": {...}}}}

CANVAS_TOOLS: list[dict] = [
    {
        "toolSpec": {
            "name": "add_sticky",
            "description": (
                "Place a sticky note at a specific position on the canvas. "
                "Use this to contribute an idea, surface a question, or add context "
                "near related content. Keep text 10 to 15 words — a full thought, not a fragment. "
                "Color semantics: yellow=idea, blue=question, green=insight, "
                "red=action item, orange=risk/warning, purple=theme/category."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "x":     {"type": "number", "description": "Canvas X position (0–2000)"},
                        "y":     {"type": "number", "description": "Canvas Y position (0–2000)"},
                        "text":  {"type": "string", "description": "Sticky content (10–15 words, a full thought)"},
                        "color": {
                            "type": "string",
                            "enum": ["yellow", "blue", "green", "red", "orange", "purple"],
                            "description": "Choose color semantically, not decoratively",
                        },
                        "author": {"type": "string", "description": "Author of the sticky"},
                    },
                    "required": ["x", "y", "text", "color"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "group_stickies",
            "description": (
                "Group a set of existing sticky notes under a shared label. "
                "Use when 4+ stickies share a theme the team hasn't named yet. "
                "Naming a cluster is one of the highest-value moves you can make."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "sticky_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of stickies to include in this group",
                        },
                        "label": {
                            "type": "string",
                            "description": "Cluster name (e.g. 'User Pain Points', 'Open Questions')",
                        },
                        "color": {
                            "type": "string",
                            "enum": ["gray", "blue", "green", "purple", "amber", "red"],
                            "description": "Group color",
                        },
                    },
                    "required": ["sticky_ids", "color"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "add_section",
            "description": (
                "Add a rectangular section outline to the canvas. "
                "Use to announce a phase, name a region, or give the team "
                "a shared frame of reference. Keep title 1–5 words."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Section title (1–5 words)"},
                        "x":    {"type": "number", "description": "Canvas X position"},
                        "y":    {"type": "number", "description": "Canvas Y position"},
                        "width": {"type": "number", "description": "Section width"},
                        "height": {"type": "number", "description": "Section height"},
                        "color": {
                            "type": "string",
                            "enum": ["gray", "blue", "green", "purple", "amber", "red"],
                            "description": "Section color",
                        },
                    },
                    "required": ["title", "x", "y", "width", "height", "color"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "add_image",
            "description": (
                "Generate and place an image on the canvas from a text prompt. "
                "Use sparingly — only when a visual genuinely shortens the conversation. "
                "The backend handles fal.ai / Replicate and returns the URL."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "prompt":  {"type": "string", "description": "Image generation prompt"},
                        "x":       {"type": "number", "description": "Canvas X position"},
                        "y":       {"type": "number", "description": "Canvas Y position"},
                        "width":   {"type": "number", "description": "Canvas units (default 300)"},
                        "height":  {"type": "number", "description": "Canvas units (default 200)"},
                        "caption": {"type": "string", "description": "Label shown below image"},
                    },
                    "required": ["prompt", "x", "y"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "counterargument",
            "description": (
                "Place a contrarian sticky that challenges the dominant direction of thinking on the canvas. "
                "ONLY use this when 5 or more stickies share the same theme, framing, or solution direction — "
                "meaning the team is converging too fast on one angle and needs a jolt.\n\n"
                "The counterargument should NOT be another idea in the same direction. "
                "It must reframe, challenge, or invert the assumption behind the cluster. "
                "Examples: if 5 stickies are all 'ways to save money', counter with 'earn more instead'. "
                "If 5 stickies are all 'add more features', counter with 'remove features entirely'.\n\n"
                "Write the text as a direct, punchy challenge — 10 to 15 words. "
                "Place it visually near but slightly outside the cluster it is challenging."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "x":     {"type": "number", "description": "Canvas X position, near the cluster"},
                        "y":     {"type": "number", "description": "Canvas Y position, near the cluster"},
                        "text":  {"type": "string", "description": "The contrarian challenge (10–15 words)"},
                        "challenged_theme": {"type": "string", "description": "One-line description of the pattern being challenged"},
                    },
                    "required": ["x", "y", "text", "challenged_theme"],
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "do_nothing",
            "description": (
                "Do nothing. Use this tool whenever the input does not have a clear action intent "
                "(add, organize, question, connect). When in doubt, do nothing.\n\n"
                "Always do_nothing for:\n"
                "- Filler words: 'you know', 'um', 'uh', 'okay', 'wait', 'like', 'so', 'right', 'yeah', 'hmm', 'well'\n"
                "- Incomplete thoughts: single nouns, verb fragments, anything under 4 words that is not a command\n"
                "- Social noise: greetings, 'thanks', 'cool', 'nice', 'okay great', 'got it', 'sure' — acknowledgements with no action intent\n"
                "- Any offensive, discriminatory, or hostile language — never engage, always do_nothing\n"
                "- Repetition: input that is semantically identical to something already on the canvas\n"
                "- Mid-thought fragments: 'I think maybe we should...', 'what if...', 'hmm perhaps' — wait for a complete idea\n\n"
                "Act only when input has a clear, complete intent. Silence is better than noise."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {},
                }
            },
        }
    },
    {
        "toolSpec": {
            "name": "suggest",
            "description": (
                "Propose an action as a semi-transparent preview on the canvas. "
                "The team must explicitly approve or dismiss it before it commits. "
                "Use when you have a useful idea but aren't sure it fits the current direction. "
                "Always explain your reasoning — that's what makes suggestions useful."
            ),
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Why you're proposing this (1–2 sentences)",
                        },
                        "action": {
                            "type": "string",
                            "enum": ["add_sticky", "group_stickies", "add_section", "add_image"],
                            "description": "Type of action to propose",
                        },
                        "action_params": {
                            "type": "object",
                            "description": "Full params for action type — same schema as the direct tool",
                        },
                    },
                    "required": ["reason", "action", "action_params"],
                }
            },
        }
    },
]

TOOL_CONFIG = {
    "tools": CANVAS_TOOLS,
    "toolChoice": {"auto": {}},   # Claude decides when to use tools
}


# ─────────────────────────────────────────────────────────────────────────────
# System prompt
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an AI brainstorming collaborator embedded inside a shared canvas workspace.

You are NOT a chatbot in a sidebar.
You are a spatial participant — you see the canvas, you act on it,
you place things, organize them, connect them.

─── HOW YOU READ THE CANVAS ───────────────────────────────────────────────────
Every message includes a live snapshot of the canvas: element IDs, positions,
content, and who placed each item. Read it carefully before acting.
- What themes are emerging?
- What clusters haven't been named yet?
- What relationships are implied but undrawn?
- What's missing that a thoughtful person would add?

─── HOW YOU ACT ────────────────────────────────────────────────────────────────
1. Act on the canvas — use the tools. Don't just describe what you'd do.
2. Be spatial — WHERE you place something communicates meaning.
3. Write stickies as full thoughts — 10 to 15 words each.
4. Name clusters — if you see 4+ stickies sharing a theme, group them.
5. Draw connections — if two ideas are clearly linked, make that visible.
6. Default to `suggest` unless you're certain — let the team approve bold moves.
7. React to what's there before adding more — name it, question it, connect it.

─── TONE ───────────────────────────────────────────────────────────────────────
- Curious collaborator, not an executor. Show your thinking.
- When something interesting is on the canvas, react to it with a question or observation.
- Ask more than you assert — a blue sticky question is worth more than three answers.
- Surprise the team occasionally — a reframe or unexpected connection is gold.


─── PROACTIVE BEHAVIOR ─────────────────────────────────────────────────────────
You may receive a canvas snapshot without a user message.
Act if: 5+ ungrouped stickies share a theme → cluster them.
        8+ stickies, zero labels → add structural headers.
        An obvious next move exists nobody has taken.
If nothing useful: stay silent. Don't force it.
When you notice something — a tension, a gap, an unanswered question — name it.
Don't wait to be asked. But suggest, don't impose.


─── PLACEMENT ──────────────────────────────────────────────────────────────────
The canvas state includes "User cursor position: (x, y)".
Always place new shapes near that position unless a different location is
clearly more meaningful (e.g. grouping near existing related content).
Offset each shape slightly (±50–150px) so they don't stack on top of each other.

─── LIMITS ─────────────────────────────────────────────────────────────────────
No long paragraphs. No restating what's already there. Max 4–5 actions per turn.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Canvas state → readable context block
# ─────────────────────────────────────────────────────────────────────────────

def _richtext_to_plain(rt) -> str:
    """Recursively extract plain text from a ProseMirror JSON object."""
    if not rt or not isinstance(rt, dict):
        return ""
    if rt.get("type") == "text":
        return rt.get("text", "")
    return " ".join(
        _richtext_to_plain(child)
        for child in rt.get("content", [])
    ).strip()


def _extract_text(el: dict) -> str:
    props = el.get("props") or {}
    rich = props.get("richText")
    if rich:
        return _richtext_to_plain(rich)
    # fallback: flat text fields (legacy / non-geo shapes)
    return props.get("text") or el.get("text") or el.get("label") or el.get("caption") or ""


def _format_canvas_context(canvas_state: dict) -> str:
    elements: list[dict] = canvas_state.get("elements", [])
    active_users: list[str] = canvas_state.get("active_users", [])

    cursor = canvas_state.get("cursor", {})
    cx = round(cursor.get("x", 200))
    cy = round(cursor.get("y", 200))

    lines = ["[CANVAS STATE]"]
    lines.append(f"Active collaborators: {', '.join(active_users) or 'none listed'}")
    lines.append(f"User cursor position: ({cx}, {cy})")
    lines.append(f"Total elements: {len(elements)}")

    if not elements:
        lines.append("Canvas is empty.")
        return "\n".join(lines)

    # Collect direct instructions written in [bracket] format
    instructions = []
    for el in elements:
        text = _extract_text(el)
        if text.startswith("[") and text.endswith("]"):
            instructions.append(text[1:-1].strip())

    if instructions:
        lines.append("")
        lines.append("DIRECT INSTRUCTIONS FROM USER (respond to these immediately):")
        for inst in instructions:
            lines.append(f"  → {inst}")

    lines.append("")
    by_type: dict[str, list[dict]] = {}
    for el in elements:
        by_type.setdefault(el.get("type", "unknown"), []).append(el)

    for el_type, items in sorted(by_type.items()):
        lines.append(f"  {el_type.upper()}S ({len(items)}):")
        for el in items:
            el_id  = el.get("id", "?")
            x, y   = round(el.get("x", 0)), round(el.get("y", 0))
            text   = _extract_text(el)
            author = el.get("author", "")
            members = ""
            if el_type == "group" and el.get("sticky_ids"):
                members = f" ← {el['sticky_ids']}"
            author_tag = f" [by {author}]" if author else ""
            if text.endswith("##"):
                lines.append(f"    [{el_id}] @({x},{y})  [IMAGE PROMPT: {text[:-2].strip()}]{author_tag}")
            elif text.endswith("@@"):
                lines.append(f"    [{el_id}] @({x},{y})  [VIDEO PROMPT: {text[:-2].strip()}]{author_tag}")
            else:
                lines.append(f"    [{el_id}] @({x},{y})  \"{text}\"{author_tag}{members}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Message builder  — Bedrock Converse format
# ─────────────────────────────────────────────────────────────────────────────
# Bedrock requires content to always be a list of typed blocks:
#   {"role": "user",      "content": [{"text": "..."}]}
#   {"role": "assistant", "content": [{"text": "..."}, {"toolUse": {...}}]}
#   {"role": "user",      "content": [{"toolResult": {...}}]}

def build_messages(
    canvas_state: dict,
    user_message: str | None,
    conversation_history: list[dict],
) -> list[dict]:
    canvas_context = _format_canvas_context(canvas_state)

    if user_message:
        text = f"{canvas_context}\n\n---\n\nUser: {user_message}"
    else:
        text = (
            f"{canvas_context}\n\n---\n\n"
            "[Proactive check — no user message. "
            "Contribute if genuinely useful. Stay silent if not.]"
        )

    new_turn = {"role": "user", "content": [{"text": text}]}
    return conversation_history + [new_turn]


# ─────────────────────────────────────────────────────────────────────────────
# Core API call  (async via asyncio.to_thread — boto3 is sync)
# ─────────────────────────────────────────────────────────────────────────────

async def call_claude(
    canvas_state: dict,
    user_message: str | None,
    conversation_history: list[dict],
) -> AgentResponse:
    """
    Main entry point. Called by the FastAPI route handler and the proactive loop.
    boto3 is synchronous; we offload to a thread so FastAPI stays non-blocking.
    """
    messages = build_messages(canvas_state, user_message, conversation_history)

    def _sync_call() -> dict:
        client = _make_bedrock_client()
        return client.converse(
            modelId=MODEL_ID,
            system=[{"text": SYSTEM_PROMPT}],
            messages=messages,
            toolConfig=TOOL_CONFIG,
        )

    response = await asyncio.to_thread(_sync_call)
    return _parse_response(response, messages)


# ─────────────────────────────────────────────────────────────────────────────
# Response parser
# ─────────────────────────────────────────────────────────────────────────────
# Bedrock response structure:
#   response["stopReason"]               → "tool_use" | "end_turn" | "max_tokens"
#   response["output"]["message"]        → {"role": "assistant", "content": [...]}
#   content block types:
#     {"text": "..."}
#     {"toolUse": {"toolUseId": "...", "name": "...", "input": {...}}}

def _parse_response(response: dict, messages: list[dict]) -> AgentResponse:
    actions: list[AgentAction] = []
    suggestions: list[AgentAction] = []
    reply_text: str | None = None

    assistant_message = response["output"]["message"]   # {"role": "assistant", "content": [...]}
    stop_reason = response.get("stopReason", "end_turn")
    tools_used = [b["toolUse"]["name"] for b in assistant_message.get("content", []) if "toolUse" in b]
    print(f"[claude] stop_reason={stop_reason} tools={tools_used}")

    for block in assistant_message.get("content", []):
        if "text" in block:
            stripped = block["text"].strip()
            if stripped:
                reply_text = stripped

        elif "toolUse" in block:
            tu        = block["toolUse"]
            tool_name = tu["name"]
            params    = tu["input"]        # already a dict — Bedrock deserializes JSON
            tool_id   = tu["toolUseId"]

            if tool_name == "do_nothing":
                pass  # intentional no-op
            elif tool_name == "counterargument":
                # Convert to a purple add_sticky so Canvas.tsx needs no changes
                actions.append(AgentAction(
                    tool="add_sticky",
                    params={
                        "x": params.get("x", 200),
                        "y": params.get("y", 200),
                        "text": params.get("text", ""),
                        "color": "purple",
                        "author": "claude",
                    },
                    tentative=False,
                    tool_use_id=tool_id,
                ))
            elif tool_name == "suggest":
                suggestions.append(AgentAction(
                    tool="suggest",
                    params={
                        "action": params["action"],
                        "action_params": params["action_params"],
                        "reason": params.get("reason"),
                    },
                    tentative=True,
                    reasoning=params.get("reason"),
                    tool_use_id=tool_id,
                ))
            else:
                actions.append(AgentAction(
                    tool=tool_name,
                    params=params,
                    tentative=False,
                    tool_use_id=tool_id,
                ))

    # Append assistant turn + synthetic toolResult to satisfy Bedrock's contract
    tool_results = [
        {"toolResult": {"toolUseId": b["toolUse"]["toolUseId"], "content": [{"text": "ok"}], "status": "success"}}
        for b in assistant_message.get("content", [])
        if "toolUse" in b
    ]
    updated_history = messages + [assistant_message]
    if tool_results:
        updated_history += [{"role": "user", "content": tool_results}]

    return AgentResponse(
        actions=actions,
        suggestions=suggestions,
        reply_text=reply_text,
        stop_reason=stop_reason,
        updated_history=updated_history,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Proactive trigger heuristic
# ─────────────────────────────────────────────────────────────────────────────

def should_trigger_proactive(canvas_state: dict) -> bool:
    """Called by the background polling loop in main.py every ~60 seconds."""
    elements: list[dict] = canvas_state.get("elements", [])

    stickies = [e for e in elements if e.get("type") == "sticky"]
    labels   = [e for e in elements if e.get("type") == "label"]
    groups   = [e for e in elements if e.get("type") == "group"]

    grouped_ids: set[str] = set()
    for g in groups:
        grouped_ids.update(g.get("sticky_ids", []))

    ungrouped = [s for s in stickies if s.get("id") not in grouped_ids]

    if len(ungrouped) >= 5:
        return True
    if len(stickies) >= 8 and len(labels) == 0 and len(groups) == 0:
        return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Image generation handler
# ─────────────────────────────────────────────────────────────────────────────

def _higgsfield_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv('HIGGSFIELD_API_KEY', 'f660854329d246920f0713a563f99fd2d0274d5617ea470fc37e185bd8cd684b')}",
    }


EXPORT_SYSTEM_PROMPT = """\
You are a session summarizer for a collaborative canvas brainstorming tool.
You will receive a list of canvas elements (stickies, sections, groups, images).
Write a clean, structured markdown summary of the session covering:
1. **Key Themes** — the main topics that emerged
2. **Ideas & Insights** — notable ideas placed on the canvas
3. **Open Questions** — any questions or unresolved tensions
4. **Action Items** — anything that sounds like a next step or task
5. **Session Overview** — one short paragraph describing what the team worked on

Be concise. Use bullet points. Do not invent content not present on the canvas.
"""


async def generate_summary(shapes: list[dict]) -> str:
    """Generate a textual markdown summary of the canvas using Claude."""
    lines = ["[CANVAS EXPORT]\n"]
    for shape in shapes:
        props = shape.get("props") or {}
        rich = props.get("richText")
        if rich and isinstance(rich, dict):
            def collect(node):
                if node.get("type") == "text":
                    return node.get("text", "")
                return " ".join(collect(c) for c in node.get("content", []))
            text = collect(rich).strip()
        else:
            text = str(props.get("text") or "").strip()
        if not text:
            continue
        x, y = round(shape.get("x", 0)), round(shape.get("y", 0))
        lines.append(f"- [{shape.get('type', 'shape')} @({x},{y})]: {text}")

    canvas_text = "\n".join(lines)

    def _sync_call() -> dict:
        client = _make_bedrock_client()
        return client.converse(
            modelId=MODEL_ID,
            system=[{"text": EXPORT_SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": canvas_text}]}],
        )

    response = await asyncio.to_thread(_sync_call)
    for block in response["output"]["message"].get("content", []):
        if "text" in block:
            return block["text"].strip()
    return "No summary could be generated."


async def generate_image(prompt: str) -> str | None:
    """Generate an image using the Reve API."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                f"https://platform.higgsfield.ai/reve",
                json={"prompt": prompt, "aspect_ratio": "4:3", "input_images": []},
                headers=_higgsfield_headers(),
                timeout=60.0
            )
            print(f"[image] status={res.status_code} body={res.text[:200]}")
            res.raise_for_status()
            data = res.json()
            return data.get("url") or data.get("image_url")
    except Exception as e:
        print(f"Image generation failed for prompt '{prompt}': {e}")
        return None


async def generate_video(prompt: str, duration: int = 6) -> str | None:
    """Generate a video using the Hailuo API."""
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://platform.higgsfield.ai/minimax/hailuo-2.3/standard/text-to-video",
                json={"prompt": prompt, "duration": duration, "prompt_optimizer": True},
                headers=_higgsfield_headers(),
                timeout=60.0
            )
            res.raise_for_status()
            data = res.json()
            return data.get("url") or data.get("video_url")
    except Exception as e:
        print(f"Video generation failed for prompt '{prompt}': {e}")
        return None