import time
import os
import boto3
import json

dynamodb = boto3.client("dynamodb")


def retrieve_job_info(job_name: str) -> tuple[str, str]:
    job_table = os.environ.get("JOB_TABLE", None)

    if not job_table:
        raise ValueError("JOB_TABLE environment variable is not set.")

    try:
        job_response = dynamodb.get_item(
            TableName=job_table,
            Key={"job_name": {"S": job_name}},
        )

        job_item = job_response.get("Item", None)
        if job_item is None:
            raise ValueError(f"No job found with name: {job_name}")

        config_id = job_item.get("config_id", {}).get("S", None)
        if config_id is None:
            raise ValueError(f"No config ID found in job table for job: {job_name}")

        input_s3_path = job_item.get("input_s3_path", {}).get("S", None)
        if input_s3_path is None:
            raise ValueError(f"No input S3 path found in job table for job: {job_name}")

        return config_id, input_s3_path

    except Exception as e:
        raise ValueError(f"Error retrieving job info: {str(e)}") from e


def retrieve_config(config_id: str) -> dict:
    config_table = os.environ.get("CONFIG_TABLE", None)

    if not config_table:
        raise ValueError("CONFIG_TABLE environment variable is not set.")

    config = None
    try:
        config_response = dynamodb.get_item(
            TableName=config_table,
            Key={"config_id": {"S": config_id}},
        )
        config = config_response.get("Item", {}).get("config_data", None)
    except Exception as e:
        raise ValueError(f"Error retrieving config: {str(e)}") from e

    if config is None:
        raise ValueError(f"No config found for config_id: {config_id}")

    return config


def handler(event, context):
    job_name = event.get("jobName")

    if not job_name:
        raise ValueError("jobName is required in the event")

    config_id, input_s3_path = retrieve_job_info(job_name)
    config = retrieve_config(config_id)

    print(
        f"Record processor got job name: {job_name} with config ID: {config_id} and input S3 path: {input_s3_path}"
    )
    print(f"Config: {json.dumps(config, indent=2)}")

    time.sleep(2)

    # Pass job name forward to next state
    return {"statusCode": 200, "jobName": job_name}
