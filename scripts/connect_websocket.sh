#!/bin/bash

WS_ENDPOINT=$1
JOB_NAME="report_sample"

# URL-encode the job name
ENCODED_JOB_NAME=$(echo -n "$JOB_NAME" | python3 -c "import urllib.parse; print(urllib.parse.quote(input()))")

# Include the encoded job name as a query parameter in the URL
wscat -c "${WS_ENDPOINT}?jobName=${ENCODED_JOB_NAME}" 

