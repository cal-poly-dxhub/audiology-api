#!/bin/bash

WS_ENDPOINT=$1
JOB_ID=$2

# URL-encode the job name
ENCODED_JOB_ID=$(echo -n "$JOB_ID" | python3 -c "import urllib.parse; print(urllib.parse.quote(input()))")

echo "Using job ID: $JOB_ID"

# Include the encoded job name as a query parameter in the URL
wscat -c "${WS_ENDPOINT}?jobId=${ENCODED_JOB_ID}" 

