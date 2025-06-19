import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """
    Responds to put events.
    """

    try:
        logger.debug("Received event:", json.dumps(event, indent=2))

        records = event.get("Records", [])
        responses = []

        for record in records:
            event_name = record.get("eventName", "")
            if event_name == "ObjectCreated:Put":
                bucket_name = record["s3"]["bucket"]["name"]
                object_key = record["s3"]["object"]["key"]

                responses.append({
                    "action": "put",
                    "bucket": bucket_name,
                    "key": object_key
                })
                logger.info(f"Responding to put: {object_key} in bucket {bucket_name}")

        return {
            "statusCode": 200,
            "body": json.dumps(responses)
        }

    except Exception as e:
        logger.error(f"Error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

