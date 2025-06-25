import json
import boto3
import os


dynamodb = boto3.client("dynamodb")
job_table = os.getenv("JOB_TABLE", None)


def handle_connect(connection_id: str, domain_name: str, headers: dict) -> dict:
    """
    Stores the connection ID in Dynamo, taking a Job-Name in headers.
    """
    job_name = headers.get("Job-Name")

    if not job_table:
        return {
            "statusCode": 500,
            "body": "Job table name is not set in environment variables.",
        }

    if not job_name:
        return {
            "statusCode": 400,
            "body": "Job-Name header is required.",
        }

    if not job_exists(job_name):
        return {
            "statusCode": 400,
            "body": f"Job with name {job_name} does not exist.",
        }

    try:
        # Update job table with connection ID and domain name
        response = dynamodb.update_item(
            TableName=job_table,
            Key={"job_name": {"S": job_name}},
            UpdateExpression="SET connection_id = :connection_id, domain_name = :domain_name",
            ExpressionAttributeValues={
                ":connection_id": {"S": connection_id},
                ":domain_name": {"S": domain_name},
            },
            ReturnValues="UPDATED_NEW",
        )

        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status_code == 200:
            print(f"Connection {connection_id} successfully stored in DynamoDB.")
        else:
            print(
                f"Failed to store connection {connection_id} in DynamoDB. Status code: {status_code}"
            )
            return {
                "statusCode": 500,
                "body": f"Failed to store connection {connection_id} in DynamoDB.",
            }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error connecting websocket: {str(e)}",
        }

    return {
        "statusCode": 200,
        "body": "Connected.",
    }


def job_exists(job_name: str) -> bool:
    """
    Checks if a job with the given name already exists in DynamoDB.
    """

    if not job_table:
        raise ValueError("Job table name is not set in environment variables.")

    try:
        response = dynamodb.get_item(
            TableName=job_table,
            Key={"job_name": {"S": job_name}},
        )
        return "Item" in response
    except Exception as e:
        raise ValueError(f"Error checking job existence: {str(e)}") from e


def handle_disconnect(connection_id: str) -> dict:
    """
    Handles the $disconnect route for WebSocket disconnections.
    """

    if not job_table:
        return {
            "statusCode": 500,
            "body": "Job table name is not set in environment variables.",
        }

    try:
        # TODO: need to delete by job id or index by connnection id
        response = dynamodb.delete_item(
            TableName=job_table,
            Key={"connection_id": {"S": connection_id}},
        )

        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status_code == 200:
            print(f"Connection {connection_id} successfully removed from DynamoDB.")
        else:
            print(
                f"Failed to remove connection {connection_id} from DynamoDB. Status code: {status_code}"
            )
            return {
                "statusCode": 500,
                "body": f"Failed to remove connection {connection_id} from DynamoDB.",
            }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": f"Error disconnecting websocket: {str(e)}",
        }

    return {
        "statusCode": 200,
        "body": "Disconnected.",
    }


def handle_default(event: dict, connection_id: str, domain_name: str, stage: str):
    body = json.loads(event.get("body", "{}"))

    try:
        send_to_client(connection_id, domain_name, stage, body)
    except Exception as e:
        print(f"Error sending message: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Error sending message: {str(e)}",
        }

    return {
        "statusCode": 200,
        "body": "Message processed.",
    }


def send_to_client(
    connection_id: str, domain_name: str, stage: str, data: dict
) -> None:
    try:
        apigw_management_api = boto3.client(
            "apigatewaymanagementapi", endpoint_url=f"https://{domain_name}/{stage}"
        )
        apigw_management_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({"message": f'Echo: {data.get("message", "")}'}),
        )
    except Exception as e:
        print(f"Error sending message to client: {str(e)}")
        raise e


def handler(event, context):
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")
    domain_name = event.get("requestContext", {}).get("domainName")
    stage = event.get("requestContext", {}).get("stage")
    headers = event.get("headers", {})

    print("Domain name:", domain_name)
    print("Stage:", stage)
    print("Connection ID:", connection_id)
    print(f"Route key: {route_key}")

    print(f"Received event: {json.dumps(event, indent=2)}")
    print("Got message")

    return_val = None
    match route_key:
        case "$connect":
            print("Handling connect route")
            return_val = handle_connect(connection_id, domain_name, headers)

        case "$disconnect":
            print("Handling disconnect route")
            return_val = handle_disconnect(connection_id)

        case "$default":
            print("Handling default route")
            return_val = handle_default(event, connection_id, domain_name, stage)

        case _:
            print("Route not handled in match case")
            return_val = {
                "statusCode": 400,
                "body": f"Unhandled route: {route_key}",
            }

    print(f"Returning: {json.dumps(return_val, indent=2)}")
    return return_val
