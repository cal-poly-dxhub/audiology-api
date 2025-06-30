#!/bin/bash

# Uploads a test base-64 encoded json file of dummy records to the upload API endpoint.

API_ID=$1
REGION="us-west-2"

curl -X POST "https://$API_ID.execute-api.$REGION.amazonaws.com/prod/upload" \
  -H "Content-Type: application/json" \
  -d '{"job_name": "report_sample", "config_id": "TestConfig", "institution_id": "Redcap"}' > upload_out.json

