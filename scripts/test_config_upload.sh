#!/bin/bash

# Check if both arguments are provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <path_to_json_file> <config_id>"
    echo "Example: $0 ./config.json my_config_name"
    exit 1
fi

JSON_FILE="$1"
CONFIG_ID="$2"
API_URL="<Your stack's /upload_config resource endpoint>"
API_KEY=${AUDIOLOGY_API_KEY}
if [ -z "$API_KEY" ]; then
  echo "Error: AUDIOLOGY_API_KEY is not set."
  exit 1
fi

# Check if JSON file exists
if [ ! -f "$JSON_FILE" ]; then
    echo "Error: File '$JSON_FILE' not found"
    exit 1
fi

# Read and validate JSON file
if ! jq empty "$JSON_FILE" 2>/dev/null; then
    echo "Error: '$JSON_FILE' contains invalid JSON"
    exit 1
fi

CONFIG_DATA=$(cat "$JSON_FILE")

# Create the payload
PAYLOAD=$(jq -n \
    --arg config_name "$CONFIG_ID" \
    --argjson config_data "$CONFIG_DATA" \
    '{config_name: $config_name, config_data: $config_data}')

echo "Uploading config '$CONFIG_ID' from '$JSON_FILE'"

# Make the request
curl -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $API_KEY" \
    -d "$PAYLOAD" \
    -s | jq .
    # -w "\nHTTP Status: %{http_code}\n" \
