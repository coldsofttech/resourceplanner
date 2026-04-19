"""
apps/ai/client.py
-----------------
Generic AI provider adapters.  This module has no knowledge of projects,
labels, or any domain concept — it only knows how to talk to AI APIs.

Three concrete clients are supported:

  AnthropicClient      — Anthropic Messages API via the anthropic SDK.
  BedrockRoleClient    — AWS Bedrock using an IAM Role (instance profile /
                         ECS task role / AWS_* environment variables).
                         No credentials are stored in the database.
  BedrockUserClient    — AWS Bedrock using an explicit IAM User access key
                         and secret stored in the Configurations store.
                         Use this for local / on-premise deployments.

All clients expose a single method:

    complete(prompt: str, max_tokens: int = 256) -> str

Configuration keys consumed (from apps.configurations.services.ConfigurationService):

    AI_PROVIDER            anthropic | bedrock            (default: anthropic)
    AI_MODEL               model identifier string        (required)
    AI_ANTHROPIC_API_KEY   sk-ant-...                     (Anthropic only)
    AI_BEDROCK_REGION      AWS region                     (Bedrock, default: us-east-1)
    AI_BEDROCK_AUTH_MODE   role | user                    (Bedrock, default: role)
    AI_BEDROCK_IAM_KEY     AWS access key ID              (Bedrock user mode only)
    AI_BEDROCK_IAM_SECRET  AWS secret access key          (Bedrock user mode only)

Installation:
    pip install anthropic --break-system-packages   # for Anthropic
    pip install boto3 --break-system-packages        # for Bedrock
"""

import json
import logging

logger = logging.getLogger(__name__)


class AIClientFactory:
    """
    Reads AI_PROVIDER and AI_BEDROCK_AUTH_MODE from Configurations and
    returns the appropriate client instance.
    """

    @staticmethod
    def get_client() -> "BaseAIClient":
        from apps.configurations.services import ConfigurationService

        provider = ConfigurationService.get("AI_PROVIDER", "anthropic").strip().lower()

        if provider == "bedrock":
            auth_mode = (
                ConfigurationService.get("AI_BEDROCK_AUTH_MODE", "role").strip().lower()
            )
            if auth_mode == "user":
                return BedrockUserClient()
            return BedrockRoleClient()

        return AnthropicClient()


class BaseAIClient:
    def complete(self, prompt: str, max_tokens: int = 256) -> str:
        raise NotImplementedError


class AnthropicClient(BaseAIClient):
    """
    Calls the Anthropic Messages API using the official anthropic Python SDK.

    Required configuration:
        AI_ANTHROPIC_API_KEY — your Anthropic API key (sk-ant-...)
        AI_MODEL             — e.g. claude-sonnet-4-20250514
    """

    def complete(self, prompt: str, max_tokens: int = 256) -> str:
        try:
            import anthropic
        except ImportError:
            raise RuntimeError(
                "anthropic package is not installed. "
                "Run: pip install anthropic --break-system-packages"
            )

        from apps.configurations.services import ConfigurationService

        api_key = ConfigurationService.get("AI_ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError(
                "AI_ANTHROPIC_API_KEY is not configured. "
                "Set it via the Configurations admin."
            )

        model = ConfigurationService.get("AI_MODEL", "").strip()
        if not model:
            raise ValueError("AI_MODEL is not configured.")

        logger.debug(
            "AnthropicClient.complete model=%s max_tokens=%d", model, max_tokens
        )

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()


def _bedrock_request_body(prompt: str, model: str, max_tokens: int) -> bytes:
    """
    Build the JSON body for a Bedrock InvokeModel call.

    Claude models on Bedrock use the Messages API format.
    All other models fall back to the legacy prompt/max_tokens_to_sample format.
    """
    if model.startswith("anthropic.claude"):
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        payload = {
            "prompt": prompt,
            "max_tokens_to_sample": max_tokens,
        }
    return json.dumps(payload).encode("utf-8")


def _bedrock_parse_response(body: bytes, model: str) -> str:
    """Parse an InvokeModel response body back to plain text."""
    data = json.loads(body)
    if model.startswith("anthropic.claude"):
        return data["content"][0]["text"].strip()
    return data.get("completion", "").strip()


def _bedrock_invoke(client, model: str, prompt: str, max_tokens: int) -> str:
    body = _bedrock_request_body(prompt, model, max_tokens)
    response = client.invoke_model(
        modelId=model,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    return _bedrock_parse_response(response["body"].read(), model)


class BedrockRoleClient(BaseAIClient):
    """
    Calls Bedrock with no stored credentials.  boto3 resolves credentials
    automatically via its standard chain:
      1. Environment variables (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)
      2. ~/.aws/credentials
      3. EC2 instance metadata (IMDSv2)
      4. ECS task role

    Required configuration:
        AI_MODEL           — e.g. anthropic.claude-3-5-sonnet-20241022-v2:0
        AI_BEDROCK_REGION  — e.g. us-east-1  (default: us-east-1)
    """

    def complete(self, prompt: str, max_tokens: int = 256) -> str:
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 package is not installed. "
                "Run: pip install boto3 --break-system-packages"
            )

        from apps.configurations.services import ConfigurationService

        model = ConfigurationService.get("AI_MODEL", "").strip()
        if not model:
            raise ValueError("AI_MODEL is not configured.")

        region = ConfigurationService.get("AI_BEDROCK_REGION", "us-east-1").strip()

        logger.debug(
            "BedrockRoleClient.complete model=%s region=%s max_tokens=%d",
            model,
            region,
            max_tokens,
        )

        client = boto3.client("bedrock-runtime", region_name=region)
        return _bedrock_invoke(client, model, prompt, max_tokens)


class BedrockUserClient(BaseAIClient):
    """
    Calls Bedrock with an explicit IAM user access key and secret stored in
    the Configurations store.  Use this when the server does not run on AWS
    infrastructure and cannot rely on instance metadata.

    Required configuration:
        AI_MODEL                — e.g. anthropic.claude-3-5-sonnet-20241022-v2:0
        AI_BEDROCK_REGION       — e.g. eu-west-2
        AI_BEDROCK_IAM_KEY      — IAM user access key ID
        AI_BEDROCK_IAM_SECRET   — IAM user secret access key

    The IAM user must have bedrock:InvokeModel permission on the chosen model.
    """

    def complete(self, prompt: str, max_tokens: int = 256) -> str:
        try:
            import boto3
        except ImportError:
            raise RuntimeError(
                "boto3 package is not installed. "
                "Run: pip install boto3 --break-system-packages"
            )

        from apps.configurations.services import ConfigurationService

        model = ConfigurationService.get("AI_MODEL", "").strip()
        if not model:
            raise ValueError("AI_MODEL is not configured.")

        region = ConfigurationService.get("AI_BEDROCK_REGION", "us-east-1").strip()
        iam_key = ConfigurationService.get("AI_BEDROCK_IAM_KEY", "").strip()
        iam_secret = ConfigurationService.get("AI_BEDROCK_IAM_SECRET", "").strip()

        if not iam_key or not iam_secret:
            raise ValueError(
                "AI_BEDROCK_IAM_KEY and AI_BEDROCK_IAM_SECRET must both be set "
                "when AI_BEDROCK_AUTH_MODE=user."
            )

        logger.debug(
            "BedrockUserClient.complete model=%s region=%s max_tokens=%d",
            model,
            region,
            max_tokens,
        )

        client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=iam_key,
            aws_secret_access_key=iam_secret,
        )
        return _bedrock_invoke(client, model, prompt, max_tokens)
