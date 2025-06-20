#!/bin/bash

RESPONSE_FILE="upload_out.json"
URL="$(cat upload_out.json | jq -r '.body.url')"

echo "Uploading to $URL"

curl -X PUT \
  -T "$1"  \
  -H "Content-Type: application/json" \
  $URL

