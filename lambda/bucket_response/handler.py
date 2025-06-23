import json
import logging
import os
import boto3
import uuid

logger = logging.getLogger()
logger.setLevel(logging.INFO)


JOB_TABLE = os.environ.get("JOB_TABLE", None)
dynamodb = boto3.client("dynamodb")


def job_exists(job_name: str) -> bool:
    """
    Checks if a job with the given name already exists in DynamoDB.
    """

    if JOB_TABLE is None:
        raise ValueError("JOB_TABLE environment variable is not set.")

    try:
        response = dynamodb.get_item(
            TableName=JOB_TABLE,
            Key={"job_name": {"S": job_name}},
        )
        return "Item" in response
    except Exception as e:
        raise ValueError(f"Error checking job existence: {str(e)}") from e


def record_job_dynamo(job_name: str, bucket_name: str, input_key: str):
    """
    Creates a job record in DynamoDB with the provided job name.
    """

    if JOB_TABLE is None:
        raise ValueError("DYNAMODB_TABLE environment variable is not set.")

    s3_path = f"s3://{bucket_name}/{input_key}"

    if job_exists(job_name):
        raise ValueError(f"Job with name {job_name} already exists.")

    job_record = {
        "job_name": {"S": job_name},
        "input_s3_path": {"S": s3_path},
        "status": {"S": "created"},
    }

    dynamodb.put_item(TableName=JOB_TABLE, Item=job_record)


def handler(event: dict, context: dict) -> dict:
    """
    Responds to put events by logging the job and triggering a
    step function response.
    """

    logger.debug("Received event:", json.dumps(event, indent=2))
    records = event.get("Records", [])

    for record in records:
        logger.debug("Processing record:", json.dumps(record, indent=2))
        event_name = record.get("eventName", "")

        # Only respond to ObjectCreated:Put events
        match event_name:
            case "ObjectCreated:Put":
                bucket_name = record["s3"]["bucket"]["name"]
                object_key = record["s3"]["object"]["key"]
                job_name = object_key.split("/")[-1].replace(".csv", "")

                try:
                    record_job_dynamo(job_name, bucket_name, object_key)
                    logger.info(f"Job {job_name} recorded successfully.")

                except ValueError as e:
                    logger.error(f"Error recording job: {str(e)}")
                    return {"statusCode": 400, "body": str(e)}

            case _:
                logger.info(f"Unhandled event type: {event_name}")

        # TODO: trigger step function here

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Event processed successfully."}),
        "headers": {"Content-Type": "application/json"},
    }
