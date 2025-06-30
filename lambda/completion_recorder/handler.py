import boto3
import os
import json

job_table = os.getenv("JOB_TABLE", None)
dynamodb = boto3.client("dynamodb")


def get_connection_details(job_table, job_name):
    try:
        # Retrieve connection_id and dnomain_name from DynamoDB
        response = dynamodb.get_item(
            TableName=job_table,
            Key={"job_name": {"S": job_name}},
            ProjectionExpression="connection_id, domain_name",
        )
        item = response.get("Item", {})

        # Extract connection_id and domain_name
        connection_id = item.get("connection_id", {}).get("S", None)
        domain_name = item.get("domain_name", {}).get("S", None)

        # Validate that both fields are present
        if not connection_id:
            raise ValueError(f"No connection ID found for job: {job_name}")
        if not domain_name:
            raise ValueError(f"No domain name found for job: {job_name}")

        print("Found connection ID:", connection_id, "and domain name:", domain_name)
        return connection_id, domain_name
    except Exception as e:
        raise ValueError(f"Error retrieving connection details: {str(e)}") from e


def place_job_s3(job_name: str, job_info: dict) -> None:
    """
    Logs the completed job JSON to S3.
    """

    bucket_name = os.getenv("OUTPUT_BUCKET_NAME", None)
    if not bucket_name:
        raise ValueError("OUTPUT_BUCKET_NAME environment variable is not set.")

    s3 = boto3.client("s3")

    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=f"completed_jobs/{job_name}.json",
            Body=json.dumps(job_info, indent=2),
            ContentType="application/json",
        )
        print(f"Successfully logged job {job_name} to S3 bucket {bucket_name}")
    except Exception as e:
        raise ValueError(f"Error logging job to S3: {str(e)}") from e


def report_job_completion(job_name: str, job_info: dict) -> None:
    """
    Obtains a websocket connection for a job if it exists and sends a report. Logs the
    completed job JSON to S3.
    """

    # TODO: error checking
    connection_id, domain_name = get_connection_details(job_table, job_name)

    if not connection_id or not domain_name:
        print(
            f"Connection ID or domain name not found for job: {job_name}, skipping report"
        )
        return

    print("reporting job info:", job_info)
    send_to_client(
        connection_id=connection_id,
        domain_name=domain_name,
        stage="prod",
        data=job_info,
    )

    place_job_s3(job_name, job_info)

    if connection_id is not None:
        print(f"Sending report to connection {connection_id}: {job_info}")


def send_to_client(
    connection_id: str, domain_name: str, stage: str, data: dict
) -> None:
    try:
        apigw_management_api = boto3.client(
            "apigatewaymanagementapi", endpoint_url=f"https://{domain_name}/{stage}"
        )
        apigw_management_api.post_to_connection(
            ConnectionId=connection_id, Data=json.dumps(data, indent=2)
        )
    except Exception as e:
        print(f"Error sending message to client: {str(e)}")
        raise e


def handler(event, context):
    """
    Requires that a jobName and result to stream back over websocket are both passed.
    """

    if job_table is None:
        raise ValueError("JOB_TABLE environment variable is not set.")

    job_name = event.get("jobName", None)
    result = event.get("result", None)

    if not job_name or not result:
        raise ValueError("Event does not contain required fields: jobName or result.")

    print(f"Job output from record processor: {result}")

    print(
        "Completion recorder invoked for job:",
        job_name,
    )

    if not job_name:
        return {
            "statusCode": 400,
            "message": "Record processor lambda did not send forward a job name.",
        }

    print("Logging for job:", job_name)

    # TODO: error checking
    report_job_completion(job_name, result)

    print("Completion recorder finished processing for job:", job_name)

    return {
        "statusCode": 200,
        "message": "Second state processing complete",
    }
