# backend/tests/test_agent_integration.py
import pytest
import os
from app.agent import call_claude


@pytest.mark.skipif(
    not os.getenv("AWS_ACCESS_KEY_ID"),
    reason="Requires AWS credentials"
)
@pytest.mark.asyncio
async def test_call_claude_real_bedrock():
    """Live test against Bedrock — skipped without AWS creds"""
    
    canvas_state = {
        "elements": [
            {
                "id": "sticky-1",
                "type": "sticky",
                "x": 100,
                "y": 100,
                "text": "User wants feedback",
                "author": "alice",
            }
        ],
        "active_users": ["alice"],
    }
    
    result = await call_claude(
        canvas_state,
        "What should we do next?",
        [],
    )
    
    # Just verify it doesn't crash and returns valid structure
    assert result.stop_reason in ["end_turn", "tool_use", "max_tokens"]
    assert isinstance(result.actions, list)
    assert isinstance(result.suggestions, list)
