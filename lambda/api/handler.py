from aws_lambda_powertools.event_handler.api_gateway import (
    ApiGatewayResolver,
    CORSConfig,
)
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger, Tracer
import boto3
from datetime import datetime
import os
import json
from botocore.utils import ClientError
import sys
import logging
import uuid

from audiology_errors.errors import ValidationError, InternalServerError
from audiology_errors.utils import handle_errors

sys.path.append("/opt/python")  # For lambda layers

cors_config = CORSConfig(
    allow_origin="*",  # or "*" for all origins
    allow_headers=["Content-Type", "Authorization"],
    expose_headers=["X-Custom-Header"],
    max_age=3600,
)
resolver = ApiGatewayResolver(cors=cors_config)
tracer = Tracer(service="audiology-api-lambda")
logger = Logger(service="audiology-api-lambda")

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")

JOB_TABLE = os.environ.get("JOB_TABLE", None)
CONFIG_TABLE_NAME = os.environ.get("CONFIG_TABLE_NAME", None)


def create_dynamo_job(
    job_name: str,
    config_id: str,
    institution_id: str,
) -> str:
    """Create a new job in the DynamoDB job table.

    Raises:
        ValidationError: If the job name already exists in the job table.
        InternalServerError: If there is an error creating the job in DynamoDB or checking job existence.

    Returns:
        str: The UUID of the created job.

    """

    job_id = str(uuid.uuid4())

    try:
        dynamodb.put_item(
            TableName=JOB_TABLE,
            Item={
                "job_id": {"S": job_id},
                "job_name": {"S": job_name},
                "config_id": {"S": config_id},
                "institution_id": {"S": institution_id},
                "status": {"S": "created"},
            },
        )
    except ClientError as e:
        logger.error(f"Error creating job in job table: {e}")
        raise InternalServerError(f"Error creating job in DynamoDB.") from e

    return job_id


def generate_presigned_url(bucket_name, file_key, mime_type) -> str:
    """Generate a pre-signed URL for uploading a file to S3.

    Raises:
        InternalServerError: If there is an error generating the pre-signed URL.

    """
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
    except ClientError as e:
        logger.error(f"Error generating pre-signed URL: {e}")
        raise InternalServerError(
            "Could not generate pre-signed URL for S3 upload."
        ) from e

    return presigned_url


@resolver.post("/upload")
@tracer.capture_method
def upload_handler():
    """Handle file upload events by generating a pre-signed URL."""
    logger.info("Received file upload event")

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

    validate_upload(json_body)

    job_name = json_body["job_name"]
    config_id = json_body["config_id"]
    institution_id = json_body["institution_id"]
    mime_type = json_body["mime_type"]

    logger.info("Job name: %s", job_name)

    job_id = create_dynamo_job(
        job_name=job_name,
        config_id=config_id,
        institution_id=institution_id,
    )

    file_key = f"input_reports/{job_id}.{supported_types[mime_type]['extension']}"

    presigned_url = generate_presigned_url(
        bucket_name=os.environ["BUCKET_NAME"],
        file_key=file_key,
        mime_type=mime_type,
    )

    logger.info(f"Generated pre-signed URL: {presigned_url}")

    return {
        "statusCode": 200,
        "body": {"url": presigned_url, "key": file_key, "job_id": job_id},
        "headers": {"Content-Type": "application/json"},
    }


def store_or_update_config(
    config_name: str,
    config_data: dict,
) -> str:
    """Create or update a config in DynamoDB, returning the action taken.

    Raises:
        InternalServerError: If there is an error storing the config in DynamoDB.

    """
    timestamp = datetime.now().isoformat()

    if not item_exists:
        item["created_at"] = {"S": timestamp}

    item = {
        "config_id": {"S": config_name},
        "config_data": {"S": json.dumps(config_data)},
        "updated_at": {"S": timestamp},
    }

    try:
        response = dynamodb.get_item(
            TableName=CONFIG_TABLE_NAME,
            Key={"config_id": {"S": config_name}},
        )
    except ClientError as e:
        logger.error(f"Error checking config existence in DynamoDB: {e}", exc_info=True)
        raise InternalServerError(
            f"Error checking config existence. Does the config exist?"
        ) from e

    item_exists = "Item" in response

    try:
        dynamodb.put_item(TableName=CONFIG_TABLE_NAME, Item=item)
    except ClientError as e:
        logger.error(f"Error storing config in DynamoDB: {e}", exc_info=True)
        raise InternalServerError(f"Error storing config in DynamoDB.") from e

    return "updated" if item_exists else "created"


@resolver.post("/upload_config")
@tracer.capture_method
def upload_config_handler():
    """Handle config upload events by storing JSON data in DynamoDB."""
    logger.info("Received config upload event")

    event = resolver.current_event
    json_body = event.json_body

    validate_upload_config(json_body)

    config_name = json_body["config_name"]
    config_data = json_body["config_data"]

    config_exists = check_config_exists(config_name)
    action = store_or_update_config(config_name, config_data)

    message = f"Config '{config_name}' successfully {action}."
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


def validate_env() -> None:
    """Validate that all required environment variables are set.

    Raises:
        InternalServerError: If any required environment variable is missing.

    """
    required_env_vars = ["JOB_TABLE", "BUCKET_NAME", "CONFIG_TABLE_NAME"]
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    if missing_vars:
        raise InternalServerError()


def validate_upload_config(json_body: dict) -> None:
    """Validate the JSON body of the config upload request.

    Raises:
        ValidationError: If any required field is missing in the JSON body.

    """
    required_fields = ["config_name", "config_data"]

    for field in required_fields:
        if field not in json_body:
            logger.error(f"Missing required field: {field}")
            raise ValidationError(f"Missing required field: {field}", field=field)


def validate_upload(json_body: dict) -> bool:
    """Validate the JSON body of the upload request.

    Raises:
        ValidationError: If any required field is missing in the JSON body.

    """
    required_fields = ["job_name", "config_id", "institution_id", "mime_type"]

    for field in required_fields:
        if field not in json_body:
            logger.error(f"Missing required field: {field}")
            raise ValidationError(f"Missing required field: {field}", field=field)


@handle_errors
def handler(event: dict, context: LambdaContext) -> dict:
    """Handle API Gateway events."""
    validate_env()

    response = resolver.resolve(event, context)
    logger.info(f"Response: {response}")

    return response
