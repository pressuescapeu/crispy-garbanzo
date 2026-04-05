# backend/tests/test_agent.py
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.agent import (
    _format_canvas_context,
    _parse_response,
    build_messages,
    call_claude,
    should_trigger_proactive,
)


class TestCanvasContext:
    """Test canvas state formatting"""
    
    def test_empty_canvas(self):
        canvas_state = {"elements": [], "active_users": []}
        result = _format_canvas_context(canvas_state)
        assert "Canvas is empty" in result
    
    def test_format_stickies(self):
        canvas_state = {
            "elements": [
                {
                    "id": "sticky-1",
                    "type": "sticky",
                    "x": 100,
                    "y": 200,
                    "text": "Test idea",
                    "author": "alice",
                }
            ],
            "active_users": ["alice", "bob"],
        }
        result = _format_canvas_context(canvas_state)
        assert "sticky" in result.lower()
        assert "alice" in result
        assert "100" in result


class TestResponseParser:
    """Test Bedrock response parsing"""
    
    def test_parse_text_only_response(self):
        response = {
            "stopReason": "end_turn",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Here's my thought"}],
                }
            },
        }
        messages = []
        
        result = _parse_response(response, messages)
        assert result.reply_text == "Here's my thought"
        assert result.stop_reason == "end_turn"
        assert len(result.actions) == 0
    
    def test_parse_tool_use_response(self):
        response = {
            "stopReason": "tool_use",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tu-123",
                                "name": "add_sticky",
                                "input": {
                                    "x": 100,
                                    "y": 200,
                                    "text": "Great idea",
                                    "color": "yellow",
                                },
                            }
                        }
                    ],
                }
            },
        }
        messages = []
        
        result = _parse_response(response, messages)
        assert len(result.actions) == 1
        assert result.actions[0].tool == "add_sticky"
        assert result.actions[0].params["x"] == 100
    
    def test_parse_suggest_response(self):
        response = {
            "stopReason": "tool_use",
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "toolUseId": "tu-456",
                                "name": "suggest",
                                "input": {
                                    "reasoning": "These could be grouped",
                                    "action_type": "group_stickies",
                                    "action_params": {
                                        "sticky_ids": ["s1", "s2"],
                                    },
                                },
                            }
                        }
                    ],
                }
            },
        }
        messages = []
        
        result = _parse_response(response, messages)
        assert len(result.suggestions) == 1
        assert result.suggestions[0].tentative is True


class TestProactiveTrigger:
    """Test heuristic for proactive actions"""
    
    def test_trigger_on_many_ungrouped_stickies(self):
        canvas_state = {
            "elements": [
                {"id": f"s{i}", "type": "sticky"} for i in range(5)
            ]
        }
        assert should_trigger_proactive(canvas_state) is True
    
    def test_trigger_on_many_stickies_no_labels(self):
        canvas_state = {
            "elements": [
                {"id": f"s{i}", "type": "sticky"} for i in range(8)
            ]
        }
        assert should_trigger_proactive(canvas_state) is True
    
    def test_no_trigger_on_few_stickies(self):
        canvas_state = {
            "elements": [
                {"id": "s1", "type": "sticky"},
                {"id": "s2", "type": "sticky"},
            ]
        }
        assert should_trigger_proactive(canvas_state) is False


@pytest.mark.asyncio
async def test_call_claude_mocked():
    """Test the main async entry point with mocked AWS"""
    
    mock_response = {
        "stopReason": "end_turn",
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"text": "Got it"}],
            }
        },
    }
    
    with patch("app.agent._make_bedrock_client") as mock_client:
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance
        mock_instance.converse.return_value = mock_response
        
        canvas_state = {"elements": [], "active_users": []}
        result = await call_claude(
            canvas_state,
            "What should we do?",
            [],
        )
        
        assert result.reply_text == "Got it"
        assert len(result.actions) == 0
