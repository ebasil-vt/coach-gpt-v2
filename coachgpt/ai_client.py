"""Shared AI client factory — detects environment and returns the appropriate client.

Local dev: ANTHROPIC_API_KEY → direct Anthropic API
AWS production: AWS_REGION → Bedrock (Claude models via cross-region inference)
"""

import os
import anthropic


def get_client():
    """Return an Anthropic client configured for the current environment."""
    if os.environ.get("AWS_REGION"):
        return anthropic.AnthropicBedrock(
            aws_region=os.environ["AWS_REGION"]
        )
    return anthropic.Anthropic()


# Model constants — override via env vars for different deployments
HAIKU = os.environ.get(
    "COACHGPT_MODEL_HAIKU",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    if os.environ.get("AWS_REGION")
    else "claude-haiku-4-5-20251001",
)
SONNET = os.environ.get(
    "COACHGPT_MODEL_SONNET",
    "us.anthropic.claude-sonnet-4-6-v1:0"
    if os.environ.get("AWS_REGION")
    else "claude-sonnet-4-6",
)
