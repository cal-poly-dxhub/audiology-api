#!/bin/bash

RESPONSE_FILE="upload_out.json"
URL="$(cat upload_out.json | jq -r '.body.url')"

echo "Uploading to $URL"

curl -X PUT \
  -L \
  -T "$1"  \
  -H "Content-Type: text/csv" \
  $URL

