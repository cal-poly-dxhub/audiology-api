from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger, Tracer
import boto3
from datetime import datetime


resolver = ApiGatewayResolver()
tracer = Tracer(service="audiology-api-lambda")
logger = Logger(service="audiology-api-lambda")

s3 = boto3.client("s3")


@resolver.post("/upload")
@tracer.capture_method
def upload_handler():
    """
    Handles file upload events by generating a pre-signed URL.
    """
    logger.info("Received file upload event")

    event = resolver.current_event
    json_body = event.json_body
    job_name = json_body.get("job_name", None)

    if job_name is None:
        logger.error("Filename is missing in the request")
        return {
            "statusCode": 400,
            "body": "Bad Request: Filename is required.",
            "headers": {"Content-Type": "application/json"},
        }

    logger.debug(f"Job name: {job_name}")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_key = f"input_reports/{stamp}/{job_name}.csv"

    # Generate a pre-signed URL for uploading the file
    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": "audiologyapistack-audiologybucket1df9aa41-6pad9bmyikok",
                "Key": file_key,
                "ContentType": "text/csv",
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

    return {
        "statusCode": 200,
        "body": {"url": presigned_url, "key": file_key},
        "headers": {"Content-Type": "application/json"},
    }


def handler(event: dict, context: LambdaContext) -> dict:
    """
    Handles API Gateway events.
    """
    return resolver.resolve(event, context)
