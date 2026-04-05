from typing import List, Optional, Union
from pydantic import BaseModel


# Canvas action from Claude
class AgentAction(BaseModel):
    tool: str
    params: dict
    tentative: bool = False
    reasoning: Optional[str] = None
    tool_use_id: Optional[str] = None


# Agent response containing actions, suggestions, and text
class AgentResponse(BaseModel):
    actions: List[AgentAction]
    suggestions: List[AgentAction]
    reply_text: Optional[str] = None
    stop_reason: str = "end_turn"
    updated_history: List[dict]


# Specific action parameter models
class AddStickyParams(BaseModel):
    x: float
    y: float
    text: str
    color: Optional[str] = None
    author: Optional[str] = None


class GroupStickiesParams(BaseModel):
    sticky_ids: List[str]
    label: Optional[str] = None
    color: Optional[str] = None


class AddLabelParams(BaseModel):
    text: str
    x: float
    y: float
    size: Optional[str] = None


class AddSectionParams(BaseModel):
    x: float
    y: float
    width: float
    height: float
    title: str
    color: Optional[str] = None


class AddConnectionParams(BaseModel):
    from_id: str
    to_id: str
    label: Optional[str] = None
    style: Optional[str] = None


class AddImageParams(BaseModel):
    prompt: str
    x: float
    y: float
    width: Optional[float] = None
    height: Optional[float] = None
    caption: Optional[str] = None


class SuggestParams(BaseModel):
    reasoning: str
    action_type: str
    action_params: dict


# Union type for all possible params
ActionParams = Union[
    AddStickyParams,
    GroupStickiesParams,
    AddLabelParams,
    AddSectionParams,
    AddConnectionParams,
    AddImageParams,
    SuggestParams,
]


# Final model that ties tool + params together
class AgentActionMessage(BaseModel):
    tool: str
    params: ActionParams