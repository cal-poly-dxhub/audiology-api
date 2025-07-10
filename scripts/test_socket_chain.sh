# Upload a sample file and listen over WebSocket

API_ID="<Your stack's API ID>"
TABLE_NAME="<Your stack's job table name>"
FILE_NAME="<Sample data to upload>"
WS_ENDPOINT="<Your stack's WebSocket endpoint>"

python scripts/clear_jobs.py "$TABLE_NAME"
bash scripts/trigger_api_upload.sh "$API_ID" # Creates upload_out.json in root dir
JOB_ID=$(jq -r '.body.job_id' upload_out.json)
echo "Job ID: $JOB_ID"

bash scripts/put_presigned.sh "$FILE_NAME"
sleep 2
bash scripts/connect_websocket.sh "$WS_ENDPOINT" "$JOB_ID"

