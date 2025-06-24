import json
import boto3


def handler(event, context):
    route_key = event.get("requestContext", {}).get("routeKey")
    connection_id = event.get("requestContext", {}).get("connectionId")
    domain_name = event.get("requestContext", {}).get("domainName")
    stage = event.get("requestContext", {}).get("stage")

    print("Domain name:", domain_name)
    print("Stage:", stage)
    print("Connection ID:", connection_id)
    print(f"Route key: {route_key}")

    print(f"Received event: {json.dumps(event, indent=2)}")
    print("Got message")
    match route_key:
        case "$connect":
            print("Got connect")
            # TODO: store connection id in dynamo
            return {"statusCode": 200, "body": "Connected."}
        case "$disconnect":
            print("Got disconnect")
            # TODO: remove connection id from dynamo
            return {"statusCode": 200, "body": "Disconnected."}
        case "$default":
            print("About to loads")
            body = json.loads(event.get("body", "{}"))
            try:
                print("Sending to client")
                send_to_client(connection_id, domain_name, stage, body)
                print("Sent to client")
            except Exception as e:
                print(f"Error sending message: {str(e)}")
                return {
                    "statusCode": 500,
                    "body": f"Error sending message: {str(e)}",
                }

            return {"statusCode": 200, "body": "Message processed."}
        case _:
            print("Route not handled in match case")
            return {"statusCode": 200, "body": "Route not handled."}


def send_to_client(connection_id, domain_name, stage, data):
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
