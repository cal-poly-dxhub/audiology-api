#!/bin/bash

# Uploads a test base-64 encoded json file of dummy records to the upload API endpoint.

API_ID="w9nd1i6701"
REGION="us-west-2"

curl -X POST "https://$API_ID.execute-api.$REGION.amazonaws.com/prod/upload" \
  -H "Content-Type: application/json" \
  -d '{"job_name": "report_sample"}' > upload_out.json

