import json
import boto3
import logging
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client("secretsmanager")


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda authorizer that validates API keys stored in Secrets Manager.

    Expected event structure:
    {
        "type": "REQUEST",
        "methodArn": "arn:aws:execute-api:...",
        "resource": "/upload",
        "path": "/upload",
        "httpMethod": "POST",
        "headers": {
            "X-API-Key": "your-api-key"
        },
        ...
    }
    """
    try:
        # Extract API key from headers
        api_key = event.get("headers", {}).get("X-API-Key") or event.get(
            "headers", {}
        ).get("x-api-key")

        if not api_key:
            logger.warning("No API key provided in request")
            raise Exception("Unauthorized")

        # Validate API key against Secrets Manager
        if not validate_api_key(api_key):
            logger.warning(f"Invalid API key provided: {api_key[:8]}...")
            raise Exception("Unauthorized")

        # Generate policy for authorized request
        policy = generate_policy("user", "Allow", event["methodArn"])

        logger.info("API key validation successful")
        return policy

    except Exception as e:
        logger.error(f"Authorization failed: {str(e)}")
        # Return deny policy
        return generate_policy("user", "Deny", event["methodArn"])


def validate_api_key(api_key: str) -> bool:
    """
    Validate API key against keys stored in Secrets Manager.

    Args:
        api_key: The API key to validate

    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Get the secret containing valid API keys
        secret_name = "audiology-api/api-keys"

        response = secrets_client.get_secret_value(SecretId=secret_name)
        secret_data = json.loads(response["SecretString"])

        # Check if the provided API key exists in the valid keys
        valid_keys = secret_data.get("api_keys", [])

        return api_key in valid_keys

    except Exception as e:
        logger.error(f"Error validating API key: {str(e)}")
        return False


def generate_policy(principal_id: str, effect: str, resource: str) -> Dict[str, Any]:
    """
    Generate IAM policy for API Gateway.

    Args:
        principal_id: The principal user identification
        effect: Allow or Deny
        resource: The resource ARN

    Returns:
        Dict containing the authorization response
    """
    auth_response = {"principalId": principal_id}

    if effect and resource:
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}
            ],
        }
        auth_response["policyDocument"] = policy_document

    # Optional: Add context that will be passed to the Lambda function
    auth_response["context"] = {
        "stringKey": "authorized_via_lambda",
        "numberKey": 123,
        "booleanKey": True,
    }

    return auth_response
