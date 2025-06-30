from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger, Tracer
import boto3
from datetime import datetime
import os
import json

from botocore.utils import ClientError


resolver = ApiGatewayResolver()
tracer = Tracer(service="audiology-api-lambda")
logger = Logger(service="audiology-api-lambda")

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")

JOB_TABLE = os.environ.get("JOB_TABLE", None)


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


def create_dynamo_job(
    job_name: str,
    config_id: str,
    institution_id: str,
) -> None:

    job_table = os.environ.get("JOB_TABLE", None)
    if job_table is None:
        raise ValueError("JOB_TABLE environment variable is not set.")

    if job_exists(job_name):
        raise ValueError(f"Job with name {job_name} already exists.")

    try:
        dynamodb.put_item(
            TableName=job_table,
            Item={
                "job_name": {"S": job_name},
                "config_id": {"S": config_id},
                "institution_id": {"S": institution_id},
                "status": {"S": "created"},
            },
        )
    except ClientError as e:
        logger.error(f"Error creating job in DynamoDB: {e}")
        raise ValueError(f"Error creating job in DynamoDB: {str(e)}") from e
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise ValueError(f"Unexpected error: {str(e)}") from e


@resolver.post("/upload")
@tracer.capture_method
def upload_handler():
    """
    Handles file upload events by generating a pre-signed URL.
    """
    logger.info("Received file upload event")

    bucket_name = os.environ.get("BUCKET_NAME", None)

    if bucket_name is None:
        logger.error("BUCKET_NAME environment variable is not set")
        return {
            "statusCode": 500,
            "body": "Internal Server Error: BUCKET_NAME not configured.",
            "headers": {"Content-Type": "application/json"},
        }

    supported_types = {
        "text/csv": {
            "extension": "csv",
        },
        "application/json": {
            "extension": "json",
        },
    }

    event = resolver.current_event
    json_body = event.json_body
    job_name = json_body.get("job_name", None)
    config_id = json_body.get("config_id", None)
    institution_id = json_body.get("institution_id", None)
    mime_type = json_body.get("mime_type", None)

    if job_name is None:
        logger.error("Filename is missing in the request")
        return {
            "statusCode": 400,
            "body": "Bad Request: Filename is required.",
            "headers": {"Content-Type": "application/json"},
        }

    if institution_id is None:
        logger.error("Institution ID is missing in the request")
        return {
            "statusCode": 400,
            "body": "Bad Request: Institution ID is required.",
            "headers": {"Content-Type": "application/json"},
        }

    if config_id is None:
        logger.error("Config ID is missing in the request")
        return {
            "statusCode": 400,
            "body": "Bad Request: Config ID is required.",
            "headers": {"Content-Type": "application/json"},
        }

    if mime_type is None:
        logger.error("MIME type is missing in the request")
        return {
            "statusCode": 400,
            "body": "Bad Request: MIME type is required.",
            "headers": {"Content-Type": "application/json"},
        }

    if mime_type not in supported_types:
        logger.error(f"Unsupported file type: {mime_type}")
        return {
            "statusCode": 400,
            "body": f"Bad Request: Unsupported file type '{mime_type}'. Supported types are {', '.join(supported_types.keys())}.",
            "headers": {"Content-Type": "application/json"},
        }

    logger.debug(f"Job name: {job_name}")
    file_key = f"input_reports/{job_name}.{supported_types[mime_type]['extension']}"

    # Generate a pre-signed URL for uploading the file
    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": file_key,
                "ContentType": mime_type,
            },
            ExpiresIn=3600,  # URL expires in 1 hour
        )
    except Exception as e:
        logger.error(f"Error generating pre-signed URL: {e}")
        return {
            "statusCode": 500,
            "body": "Internal Server Error: Could not generate pre-signed URL.",
            "headers": {"Content-Type": "application/json"},
        }

    logger.info(f"Generated pre-signed URL: {presigned_url}")

    try:
        create_dynamo_job(
            job_name=job_name,
            config_id=config_id,
            institution_id=institution_id,
        )
    except ValueError as e:
        logger.error(f"Error creating job in DynamoDB: {e}")
        return {
            "statusCode": 500,
            "body": f"Internal Server Error: {str(e)}",
            "headers": {"Content-Type": "application/json"},
        }

    return {
        "statusCode": 200,
        "body": {"url": presigned_url, "key": file_key},
        "headers": {"Content-Type": "application/json"},
    }


@resolver.post("/upload_config")
@tracer.capture_method
def upload_config_handler():
    """
    Handles config upload events by storing JSON data in DynamoDB.
    """
    logger.info("Received config upload event")

    table_name = os.environ.get("CONFIG_TABLE_NAME", None)
    if not table_name:
        logger.error("CONFIG_TABLE_NAME environment variable is not set")
        return {
            "statusCode": 500,
            "body": {
                "error": "Internal Server Error: CONFIG_TABLE_NAME not configured."
            },
            "headers": {"Content-Type": "application/json"},
        }

    event = resolver.current_event
    json_body = event.json_body

    config_name = json_body.get("config_name", None)
    config_data = json_body.get("config_data", None)

    if not config_name:
        logger.error("config_name is missing in the request")
        return {
            "statusCode": 400,
            "body": {"error": "Bad Request: config_name is required."},
            "headers": {"Content-Type": "application/json"},
        }

    if not config_data:
        logger.error("config_data is missing in the request")
        return {
            "statusCode": 400,
            "body": {"error": "Bad Request: config_data is required."},
            "headers": {"Content-Type": "application/json"},
        }

    logger.debug(f"Config name: {config_name}")

    try:
        # Check if item already exists
        try:
            response = dynamodb.get_item(
                TableName=table_name, Key={"config_id": {"S": config_name}}
            )
            item_exists = "Item" in response
        except ClientError as e:
            logger.error(f"Error checking existing item: {e}")
            return {
                "statusCode": 500,
                "body": {
                    "error": "Internal Server Error: Could not check existing config."
                },
                "headers": {"Content-Type": "application/json"},
            }

        # Store or update the config
        timestamp = datetime.now().isoformat()

        item = {
            "config_id": {"S": config_name},
            "config_data": {"S": json.dumps(config_data)},
            "updated_at": {"S": timestamp},
        }

        if not item_exists:
            item["created_at"] = {"S": timestamp}

        dynamodb.put_item(TableName=table_name, Item=item)

        action = "updated" if item_exists else "created"
        message = f"Config '{config_name}' successfully {action}."

        logger.info(f"Config {action}: {config_name}")

        return {
            "statusCode": 200,
            "body": {
                "message": message,
                "config_name": config_name,
                "action": action,
                "timestamp": timestamp,
            },
            "headers": {"Content-Type": "application/json"},
        }

    except ClientError as e:
        logger.error(f"Error storing config in DynamoDB: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal Server Error: Could not store config."},
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "body": {"error": "Internal Server Error: Unexpected error occurred."},
            "headers": {"Content-Type": "application/json"},
        }


def handler(event: dict, context: LambdaContext) -> dict:
    """
    Handles API Gateway events.
    """
    return resolver.resolve(event, context)
