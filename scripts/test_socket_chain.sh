# Upload a sample file and listen over WebSocket

API_ID="bh8yj14k33"
TABLE_NAME="AudiologyApiStack2-AudiologyJobTable1B46B45A-RYEJYTU3977G"
FILE_NAME="data/report_sample.csv"
WS_ENDPOINT="wss://2cuuwaf2bi.execute-api.us-west-2.amazonaws.com/prod"

python scripts/clear_jobs.py "$TABLE_NAME"
bash scripts/trigger_api_upload.sh "$API_ID"
bash scripts/put_presigned.sh "$FILE_NAME"
sleep 2
bash scripts/connect_websocket.sh "$WS_ENDPOINT" 

