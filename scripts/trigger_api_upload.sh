#!/bin/bash

# Uploads a test base-64 encoded json file of dummy records to the upload API endpoint.

API_ID=$1
API_KEY=$AUDIOLOGY_API_KEY
REGION="us-west-2"

if [ -z "$API_ID" ]; then
  echo "Usage: $0 <api_id>"
  exit 1
fi

if [ -z "$API_KEY" ]; then
  echo "Error: AUDIOLOGY_API_KEY is not set."
  exit 1
fi

curl -X POST "https://$API_ID.execute-api.$REGION.amazonaws.com/prod/upload" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"job_name": "report_sample", "config_id": "TestConfig", "institution_id": "CDC", "mime_type": "text/csv"}' > upload_out.json
