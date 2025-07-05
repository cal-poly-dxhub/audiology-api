# API Key Management

This document explains how to manage API keys for the Audiology API using the lambda authorizer and Secrets Manager.

## Overview

The API now uses a Lambda authorizer that validates API keys stored in AWS Secrets Manager instead of the API Gateway managed auth flow. This provides more flexibility and security.

## Managing API Keys

Use the `manage_api_keys.py` script to manage API keys:

### List all API keys
```bash
python scripts/manage_api_keys.py list
```

### Add a new API key (auto-generated)
```bash
python scripts/manage_api_keys.py add
```

### Add a specific API key
```bash
python scripts/manage_api_keys.py add --key "your-custom-api-key"
```

### Remove an API key
```bash
python scripts/manage_api_keys.py remove "api-key-to-remove"
```

## Secret Structure

The secret `audiology-api/api-keys` contains a JSON structure:
```json
{
  "api_keys": [
    "api-key-1",
    "api-key-2",
    "api-key-3"
  ]
}
```

## Using the API

Include the API key in the `X-API-Key` header when making requests:

```bash
curl -X POST https://your-api-gateway-url/upload \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"your": "data"}'
```

## Security Notes

- API keys are stored securely in AWS Secrets Manager
- The Lambda authorizer caches authorization results for 5 minutes to improve performance
- Only the first 8 and last 4 characters of API keys are shown when listing for security
- The authorizer function has minimal permissions (only read access to the secrets)

## Deployment

After making changes to the CDK code, deploy with:
```bash
cdk deploy
```

The lambda authorizer will be automatically deployed and configured with the API Gateway.
