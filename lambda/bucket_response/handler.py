import json
import logging
import os
import boto3
import uuid
import sys

sys.path.append("/opt/python")  # For lambda layers

from botocore.utils import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)


JOB_TABLE = os.environ.get("JOB_TABLE", None)
dynamodb = boto3.client("dynamodb")

step_function_arn = os.getenv("STEP_FUNCTION_ARN", None)
sfn = boto3.client("stepfunctions")


def job_exists(job_id: str) -> bool:
    """
    Checks if a job with the given name already exists in DynamoDB.
    """

    if JOB_TABLE is None:
        raise ValueError("JOB_TABLE environment variable is not set.")

    try:
        response = dynamodb.get_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
        )
        return "Item" in response
    except Exception as e:
        raise ValueError(f"Error checking job existence: {str(e)}") from e


def record_job_dynamo(job_id: str, bucket_name: str, input_key: str):
    """
    Updates the DynamoDB job record with the input s3 path and status.
    """

    if JOB_TABLE is None:
        raise ValueError("DYNAMODB_TABLE environment variable is not set.")

    s3_path = f"s3://{bucket_name}/{input_key}"

    if not job_exists(job_id):
        raise ValueError(f"Job with ID {job_id} does not exist.")

    try:
        dynamodb.update_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET input_bucket = :input_bucket, input_key = :input_key, #status = :status",
            ExpressionAttributeValues={
                ":input_bucket": {"S": bucket_name},
                ":input_key": {"S": input_key},
                ":status": {"S": "started"},
            },
            ExpressionAttributeNames={
                "#status": "status",
            },
        )

        logger.info(f"Successfully recorded job {job_id} with S3 path {s3_path}")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"DynamoDB ClientError: {error_code} - {error_message}")
        raise Exception(f"Failed to record job in DynamoDB: {error_message}")
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error recording job {job_id}: {e}")
        raise Exception(f"Failed to record job {job_id}: {str(e)}")


def trigger_record_processing(job_id: str):
    """
    Triggers the step function for record processing with the given job name.
    """

    try:
        response = sfn.start_execution(
            stateMachineArn=step_function_arn,
            input=json.dumps({"jobId": job_id}),
        )
        logger.info(
            f"Step function triggered for job {job_id}. Execution ARN: {response['executionArn']}"
        )
        return response["executionArn"]
    except Exception as e:
        raise ValueError(f"Error triggering step function: {str(e)}") from e


def handler(event: dict, context: dict) -> dict:
    """
    Responds to put events by logging the job and triggering a
    step function response.
    """
    if step_function_arn is None:
        raise ValueError("STEP_FUNCTION_ARN environment variable is not set.")

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
                job_id = os.path.splitext(object_key.split("/")[-1])[0]

                try:
                    record_job_dynamo(job_id, bucket_name, object_key)
                    logger.info(f"Job {job_id} recorded successfully.")

                except ValueError as e:
                    logger.error(f"Error recording job: {str(e)}")
                    return {"statusCode": 400, "body": str(e)}

                # TODO: more correct error handling
                try:
                    # TODO: return val
                    trigger_record_processing(job_id)
                    logger.info(f"Step function triggered for job {job_id}.")
                except ValueError as e:
                    logger.error(f"Error triggering step function: {str(e)}")
                    return {"statusCode": 500, "body": str(e)}

            case _:
                logger.info(f"Unhandled event type: {event_name}")

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Event processed successfully."}),
        "headers": {"Content-Type": "application/json"},
    }
