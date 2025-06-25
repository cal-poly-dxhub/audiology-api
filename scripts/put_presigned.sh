#!/bin/bash

FILE_NAME=$1
RESPONSE_FILE="upload_out.json"
URL="$(cat upload_out.json | jq -r '.body.url')"

echo "Uploading $FILE_NAME to $URL"

curl -X PUT \
  -L \
  -T "$FILE_NAME"  \
  -H "Content-Type: text/csv" \
  $URL

