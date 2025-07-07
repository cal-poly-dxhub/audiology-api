import json
import boto3
import logging
import os
import jwt
import requests
from typing import Dict, Any, Optional
import sys

sys.path.append("/opt/python")  # For lambda layers

logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_client = boto3.client("secretsmanager")

# Cognito configuration from environment variables
USER_POOL_ID = os.environ.get("USER_POOL_ID")
USER_POOL_CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID")

# Cache for Cognito public keys
_cognito_keys_cache = None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lambda authorizer that validates both API keys and Cognito JWT tokens.

    Expected event structure:
    {
        "type": "REQUEST",
        "methodArn": "arn:aws:execute-api:...",
        "resource": "/upload",
        "path": "/upload",
        "httpMethod": "POST",
        "headers": {
            "X-API-Key": "your-api-key"  # OR
            "Authorization": "Bearer jwt-token"
        },
        ...
    }
    """
    try:
        headers = event.get("headers", {})

        # Check for JWT token authentication first
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            logger.info("Attempting JWT token authentication")

            user_info = validate_jwt_token(token)
            if user_info:
                logger.info(
                    f"JWT validation successful for user: {user_info.get('email', 'unknown')}"
                )
                return generate_policy(
                    user_info.get("sub", "jwt-user"),
                    "Allow",
                    event["methodArn"],
                    user_info,
                )
            else:
                logger.warning("Invalid JWT token provided")
                raise Exception("Invalid JWT token")

        # Check for API key authentication if JWT is not provided
        api_key = headers.get("X-API-Key") or headers.get("x-api-key")
        if api_key:
            logger.info("Attempting API key authentication")
            if validate_api_key(api_key):
                logger.info("API key validation successful")
                return generate_policy("api-key-user", "Allow", event["methodArn"])
            else:
                logger.warning(f"Invalid API key provided: {api_key[:8]}...")
                raise Exception("Invalid API key")

        # No valid authentication method found
        logger.warning("No valid authentication method provided")
        raise Exception("Unauthorized")

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


def validate_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate JWT token from Cognito User Pool.

    Args:
        token: The JWT token to validate

    Returns:
        Dict containing user information if valid, None otherwise
    """
    try:
        if not USER_POOL_ID or not USER_POOL_CLIENT_ID:
            logger.error("Cognito configuration not found in environment variables")
            return None

        # Get Cognito public keys
        public_keys = get_cognito_public_keys()
        if not public_keys:
            logger.error("Failed to retrieve Cognito public keys")
            return None

        # Decode token header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if kid not in public_keys:
            logger.error(f"Key ID {kid} not found in Cognito public keys")
            return None

        # Get the public key
        public_key = public_keys[kid]

        # Verify and decode the token
        decoded_token = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=f"https://cognito-idp.{boto3.Session().region_name}.amazonaws.com/{USER_POOL_ID}",
        )

        # Verify either the audience or the client ID--whichever's present
        aud = decoded_token.get("aud")
        client_id = decoded_token.get("client_id")
        if aud != USER_POOL_CLIENT_ID and client_id != USER_POOL_CLIENT_ID:
            logger.error("Token audience or client_id does not match expected value")
            return None

        # Verify token use
        if decoded_token.get("token_use") != "access":
            logger.error("Token is not an access token")
            return None

        return decoded_token

    except jwt.ExpiredSignatureError:
        logger.error("JWT token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid JWT token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error validating JWT token: {str(e)}")
        return None


def get_cognito_public_keys() -> Dict[str, Any]:
    """
    Retrieve and cache Cognito public keys for JWT verification.

    Returns:
        Dict containing public keys indexed by key ID
    """
    global _cognito_keys_cache

    if _cognito_keys_cache:
        return _cognito_keys_cache

    try:
        region = boto3.Session().region_name
        jwks_url = f"https://cognito-idp.{region}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

        response = requests.get(jwks_url, timeout=10)
        response.raise_for_status()

        jwks = response.json()
        public_keys = {}

        for key in jwks.get("keys", []):
            kid = key.get("kid")
            if kid:
                # Convert JWK to PEM format for PyJWT
                public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                public_keys[kid] = public_key

        _cognito_keys_cache = public_keys
        return public_keys

    except Exception as e:
        logger.error(f"Error retrieving Cognito public keys: {str(e)}")
        return {}


def generate_policy(
    principal_id: str,
    effect: str,
    resource: str,
    user_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Generate IAM policy for API Gateway.

    Args:
        principal_id: The principal user identification
        effect: Allow or Deny
        resource: The resource ARN
        user_info: Optional user information from JWT token

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

    # Add context that will be passed to the Lambda function
    context = {}

    # Add user information to context if available
    if user_info:
        context.update(
            {
                "userId": user_info.get("sub", ""),
                "email": user_info.get("email", ""),
                "authType": "cognito",
            }
        )
    else:
        context["authType"] = "api-key"

    auth_response["context"] = context

    return auth_response
