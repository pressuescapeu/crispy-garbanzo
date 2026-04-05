from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from .ws_server import WSManager
from .agent import call_claude, generate_image, generate_video, generate_summary
from .models import AgentAction
from pydantic import BaseModel
import json
from typing import Optional

app = FastAPI()


def _shape_plain_text(shape: dict) -> str:
    """Extract plain text from a shape dict (handles richText ProseMirror JSON)."""
    props = shape.get("props") or {}
    rich = props.get("richText")
    if rich and isinstance(rich, dict):
        def collect(node):
            if node.get("type") == "text":
                return node.get("text", "")
            return " ".join(collect(c) for c in node.get("content", []))
        return collect(rich).strip()
    return str(props.get("text") or "").strip()


def _has_bracket_command(shapes: list) -> bool:
    """Return True if any shape contains a complete [command] instruction."""
    for shape in shapes:
        t = _shape_plain_text(shape)
        if t.startswith("[") and t.endswith("]") and len(t) > 2:
            return True
    return False


def _get_image_commands(shapes: list, processed_ids: set) -> list:
    """Return unprocessed shapes whose text ends with ## as image generation commands."""
    cmds = []
    for shape in shapes:
        sid = shape.get("id")
        if sid in processed_ids:
            continue
        t = _shape_plain_text(shape)
        if t.endswith("##"):
            prompt = t[:-2].strip()
            if prompt:
                cmds.append({
                    "prompt": prompt,
                    "x": shape.get("x", 200),
                    "y": shape.get("y", 200),
                    "shape_id": sid,
                })
    return cmds


def _get_video_commands(shapes: list, processed_ids: set) -> list:
    """Return unprocessed shapes whose text ends with @@ as video generation commands."""
    cmds = []
    for shape in shapes:
        sid = shape.get("id")
        if sid in processed_ids:
            continue
        t = _shape_plain_text(shape)
        if t.endswith("@@"):
            prompt = t[:-2].strip()
            if prompt:
                cmds.append({
                    "prompt": prompt,
                    "x": shape.get("x", 200),
                    "y": shape.get("y", 200),
                    "shape_id": sid,
                })
    return cmds


# ─── Sanitizers ────────────────────────────────────────────────────────────────
# Canvas.tsx maps these keys → tldraw native names via NOTE_COLOR_MAP/GROUP_COLOR_MAP.
# Valid keys are exactly what those maps accept.
# tldraw native aliases (e.g. "light-blue", "violet") are normalised here so the AI
# can send either form without breaking the frontend.

_NOTE_COLORS = {"yellow", "blue", "green", "red", "purple", "orange"}
_GROUP_COLORS = {"gray", "blue", "green", "purple", "amber", "red"}
_SUGGEST_ACTIONS = {"add_sticky", "group_stickies", "add_section", "add_image"}

# tldraw native → AI-friendly aliases so both forms are accepted
_NOTE_COLOR_ALIASES = {
    "light-blue": "blue",
    "light-green": "green",
    "violet": "purple",
    "light-violet": "purple",
    "light-red": "red",
    "grey": "gray",
}
_GROUP_COLOR_ALIASES = {
    "grey": "gray",
    "violet": "purple",
    "orange": "amber",
}


def _coerce_note_color(c) -> str:
    c = str(c).lower() if c else "yellow"
    c = _NOTE_COLOR_ALIASES.get(c, c)
    return c if c in _NOTE_COLORS else "yellow"


def _coerce_group_color(c) -> str:
    c = str(c).lower() if c else "gray"
    c = _GROUP_COLOR_ALIASES.get(c, c)
    return c if c in _GROUP_COLORS else "gray"


def _coerce_num(v, default: float) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _coerce_str(v, default: str = "") -> str:
    return str(v).strip() if v is not None else default


def _sanitize_add_sticky(p: dict) -> dict:
    return {
        "x": _coerce_num(p.get("x"), 200),
        "y": _coerce_num(p.get("y"), 200),
        "text": _coerce_str(p.get("text")) or "Note",
        "color": _coerce_note_color(p.get("color")),
        "author": _coerce_str(p.get("author")) or "claude",
    }


def _sanitize_group_stickies(p: dict) -> dict:
    ids = p.get("sticky_ids") or []
    return {
        "sticky_ids": [str(i) for i in ids if i],
        "label": _coerce_str(p.get("label")) or "Group",
        "color": _coerce_group_color(p.get("color")),
    }


def _sanitize_add_section(p: dict) -> dict:
    return {
        "x": _coerce_num(p.get("x"), 100),
        "y": _coerce_num(p.get("y"), 100),
        "width": max(_coerce_num(p.get("width"), 400), 100),
        "height": max(_coerce_num(p.get("height"), 300), 100),
        "title": _coerce_str(p.get("title")) or "Section",
        "color": _coerce_group_color(p.get("color")),
    }



def _sanitize_add_image(p: dict) -> dict:
    return {
        "x": _coerce_num(p.get("x"), 200),
        "y": _coerce_num(p.get("y"), 200),
        "prompt": _coerce_str(p.get("prompt")),
        "width": _coerce_num(p.get("width"), 280) if p.get("width") is not None else None,
        "caption": _coerce_str(p.get("caption")) if p.get("caption") else None,
        **({"image_url": p["image_url"]} if p.get("image_url") else {}),
    }


def _sanitize_suggest(p: dict) -> dict:
    action = str(p.get("action") or "")
    return {
        "action": action if action in _SUGGEST_ACTIONS else "add_sticky",
        "action_params": p.get("action_params") or {},
        "reason": _coerce_str(p.get("reason")),
    }


_SANITIZERS = {
    "add_sticky": _sanitize_add_sticky,
    "group_stickies": _sanitize_group_stickies,
    "add_section": _sanitize_add_section,
"add_image": _sanitize_add_image,
    "suggest": _sanitize_suggest,
}


def sanitize_action(action: AgentAction) -> AgentAction:
    fn = _SANITIZERS.get(action.tool)
    if fn:
        try:
            action.params = fn(action.params)
        except Exception as e:
            print(f"[sanitize_action] failed for tool={action.tool}: {e}. params={action.params}")
    return action

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ws_manager = WSManager()

# Per-room state: accumulate shapes and transcript until Claude processes
room_state = {}

class AgentRequest(BaseModel):
    roomId: str
    transcript: str
    shapes: dict

def get_room_state(room_id: str):
    """Get or create room state."""
    if room_id not in room_state:
        room_state[room_id] = {
            "shapes": [],
            "transcript": "",
            "users": set(),
            "event_count": 0,
            "conversation_history": [],
            "cursor": {"x": 200, "y": 200},
            "in_flight": False,
            "processed_image_ids": set(),
        }
    return room_state[room_id]

@app.websocket("/ws/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str):
    await ws_manager.connect(room_id, websocket)
    state = get_room_state(room_id)

    try:
        while True:
            # Read incoming message from frontend
            data = await websocket.receive_text()
            event = json.loads(data)

            # Process shape_created event
            if event.get("event") == "shape_created":
                shape = event.get("shape", {})
                user = event.get("user", "unknown")
                state["shapes"].append(shape)
                state["users"].add(user)
                state["event_count"] += 1
                if event.get("cursorX") is not None:
                    state["cursor"] = {"x": event["cursorX"], "y": event["cursorY"]}

            # Process shape_updated event — replace existing shape in state
            elif event.get("event") == "shape_updated":
                updated = event.get("shape", {})
                user = event.get("user", "unknown")
                state["users"].add(user)
                state["event_count"] += 1
                # Replace if exists, append if new
                for i, s in enumerate(state["shapes"]):
                    if s.get("id") == updated.get("id"):
                        state["shapes"][i] = updated
                        break
                else:
                    state["shapes"].append(updated)

                # ## prefix → generate image directly, bypassing Claude
                for cmd in _get_image_commands(state["shapes"], state["processed_image_ids"]):
                    state["processed_image_ids"].add(cmd["shape_id"])
                    print(f"[image] generating for prompt: {cmd['prompt']}")
                    image_url = await generate_image(cmd["prompt"])
                    if image_url:
                        action = AgentAction(
                            tool="add_image",
                            params={
                                "x": cmd["x"] + 280,
                                "y": cmd["y"],
                                "prompt": cmd["prompt"],
                                "image_url": image_url,
                                "width": 300,
                            }
                        )
                        sanitize_action(action)
                        print(f"[broadcast] tool=add_image prompt={cmd['prompt']}")
                        await ws_manager.broadcast(room_id, action.model_dump())

                # @@ suffix → generate video directly, bypassing Claude
                for cmd in _get_video_commands(state["shapes"], state["processed_image_ids"]):
                    state["processed_image_ids"].add(cmd["shape_id"])
                    print(f"[video] generating for prompt: {cmd['prompt']}")
                    video_url = await generate_video(cmd["prompt"])
                    if video_url:
                        action = AgentAction(
                            tool="add_video",
                            params={
                                "x": cmd["x"] + 280,
                                "y": cmd["y"],
                                "prompt": cmd["prompt"],
                                "video_url": video_url,
                                "width": 300,
                            }
                        )
                        print(f"[broadcast] tool=add_video prompt={cmd['prompt']}")
                        await ws_manager.broadcast(room_id, action.model_dump())

            # Process transcript_chunk event
            elif event.get("event") == "transcript_chunk":
                text = event.get("text", "")
                user = event.get("user", "unknown")
                state["transcript"] += text + " "
                state["users"].add(user)
                state["event_count"] += 1
                if event.get("cursorX") is not None:
                    state["cursor"] = {"x": event["cursorX"], "y": event["cursorY"]}

            print(f"[event] {event.get('event')} event_count={state['event_count']} in_flight={state['in_flight']} shapes={len(state['shapes'])}")
            # Trigger Claude on every 2 events or when transcript chunk arrives with content.
            # shape_updated only triggers if a complete [command] is present.
            should_trigger = (
                (state["event_count"] >= 2 and event.get("event") != "shape_updated") or
                (event.get("event") == "shape_updated" and _has_bracket_command(state["shapes"])) or
                (event.get("event") == "transcript_chunk" and event.get("text", "").strip())
            )

            if should_trigger and not state["in_flight"] and (state["shapes"] or state["transcript"].strip()):
                canvas_state = {
                    "elements": state["shapes"],
                    "active_users": list(state["users"]),
                    "cursor": state["cursor"],
                }

                user_message = None
                if state["transcript"].strip():
                    user_message = state["transcript"].strip()
                # If a bracket command triggered this call, extract it as user_message
                # so Claude gets "User: ..." framing instead of the proactive check framing
                if user_message is None:
                    for shape in state["shapes"]:
                        t = _shape_plain_text(shape)
                        if t.startswith("[") and t.endswith("]") and len(t) > 2:
                            user_message = t[1:-1].strip()
                            break

                print(f"[call_claude] user_message={user_message!r} shapes={len(state['shapes'])}")
                # Call Claude
                state["in_flight"] = True
                try:
                    agent_response = await call_claude(
                        canvas_state,
                        user_message,
                        state["conversation_history"]
                    )
                finally:
                    state["in_flight"] = False
                    state["event_count"] = 0

                # Update conversation history
                state["conversation_history"] = agent_response.updated_history

                # Generate images/videos and broadcast actions
                sticky_idx = 0
                for action in agent_response.actions:
                    if action.tool == "add_image":
                        image_url = await generate_image(action.params.get("prompt", ""))
                        if image_url:
                            action.params["image_url"] = image_url
                    elif action.tool == "add_video":
                        video_url = await generate_video(
                            action.params.get("prompt", ""),
                            action.params.get("duration", 6)
                        )
                        if video_url:
                            action.params["video_url"] = video_url

                    sanitize_action(action)

                    # Spread stickies in a grid so they don't stack on the same coords
                    if action.tool == "add_sticky":
                        col = sticky_idx % 3
                        row = sticky_idx // 3
                        action.params["x"] = action.params["x"] + col * 250
                        action.params["y"] = action.params["y"] + row * 170
                        sticky_idx += 1

                    print(f"[broadcast] tool={action.tool} params={action.params}")
                    await ws_manager.broadcast(room_id, action.model_dump())

                # Broadcast suggestions (if any)
                for suggestion in agent_response.suggestions:
                    sanitize_action(suggestion)
                    await ws_manager.broadcast(room_id, suggestion.model_dump())

                # Reset buffers for next trigger
                state["shapes"] = []
                state["transcript"] = ""

    except Exception as e:
        print(f"WebSocket error in room {room_id}: {e}")
    finally:
        ws_manager.disconnect(room_id, websocket)

@app.post("/agent")
async def agent_endpoint(request: AgentRequest):
    """Manual trigger endpoint (optional, for explicit user requests)."""
    state = get_room_state(request.roomId)

    canvas_state = {
        "elements": request.shapes.get("shapes", []) if isinstance(request.shapes, dict) else [],
        "active_users": list(state["users"]),
        "cursor": state["cursor"],
    }

    agent_response = await call_claude(
        canvas_state,
        request.transcript if request.transcript.strip() else None,
        state["conversation_history"]
    )

    # Update conversation history
    state["conversation_history"] = agent_response.updated_history

    # Generate images/videos and broadcast
    for action in agent_response.actions:
        if action.tool == "add_image":
            image_url = await generate_image(action.params.get("prompt", ""))
            if image_url:
                action.params["image_url"] = image_url
        elif action.tool == "add_video":
            video_url = await generate_video(
                action.params.get("prompt", ""),
                action.params.get("duration", 6)
            )
            if video_url:
                action.params["video_url"] = video_url

        sanitize_action(action)
        print(f"[broadcast] tool={action.tool} params={action.params}")
        await ws_manager.broadcast(request.roomId, action.model_dump())

    return {"ok": True}

@app.post("/generate-video")
async def generate_video_endpoint(prompt: str, duration: int = 6, prompt_optimizer: bool = True):
    """Endpoint for manual video generation."""
    return await generate_video(prompt, duration, prompt_optimizer)

@app.post("/generate-image")
async def generate_image_endpoint(prompt: str):
    """Endpoint for manual image generation."""
    return await generate_image(prompt)


class ExportRequest(BaseModel):
    shapes: list
    users: Optional[str] = None

@app.post("/export")
async def export_endpoint(request: ExportRequest):
    """Generate a markdown summary of the canvas from all shape text and metadata."""
    summary = await generate_summary(request.shapes)
    return {"summary": summary}
