#!/bin/bash

WS_ENDPOINT=$1
JOB_ID=$2
API_KEY=$AUDIOLOGY_API_KEY

if [ -z "$WS_ENDPOINT" ]; then
  echo "Usage: $0 <websocket_endpoint> <job_id>"
  exit 1
fi

if [ -z "$JOB_ID" ]; then
  echo "Usage: $0 <websocket_endpoint> <job_id>"
  exit 1
fi

if [ -z "$API_KEY" ]; then
  echo "Error: AUDIOLOGY_API_KEY is not set."
  exit 1
fi

# URL-encode the job name
ENCODED_JOB_ID=$(echo -n "$JOB_ID" | python3 -c "import urllib.parse; print(urllib.parse.quote(input()))")

echo "Using job ID: $JOB_ID"

# Include the encoded job name and API key as query parameters in the URL
wscat -c "${WS_ENDPOINT}?jobId=${ENCODED_JOB_ID}&ApiKey=${API_KEY}" 

