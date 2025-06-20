#!/bin/bash

# Uploads a test base-64 encoded json file of dummy records to the upload API endpoint.

API_ID="w9nd1i6701"
REGION="us-west-2"

cat data/dummy_json.json | base64 -w 0 | \
(echo -n '{"isBase64Encoded": true, "body": "'; cat -; echo '"}') | \
curl -X POST "https://$API_ID.execute-api.$REGION.amazonaws.com/prod/upload" \
  -H "Content-Type: application/json" \
  -d @-
