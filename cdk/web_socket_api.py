from aws_cdk import (
    Stack,
    Duration,
    CfnOutput,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_dynamodb as dynamodb,
    aws_logs as logs,
    aws_iam as iam,
    aws_secretsmanager as secretsmanager,
)

from constructs import Construct
from datetime import datetime


class WebSocketApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        job_table: dynamodb.Table,
        error_layer: _lambda.LayerVersion,
        user_pool_id: str,
        user_pool_client_id: str,
        api_keys_secret_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.region = Stack.of(self).region
        self.account = Stack.of(self).account

        # Create log groups first
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        access_log_group = logs.LogGroup(
            self,
            "WebSocketApiAccessLogs",
            log_group_name=f"/aws/apigateway/websocket/{construct_id}/access_{timestamp}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create WebSocket authorizer Lambda function
        websocket_authorizer = _lambda.Function(
            self,
            "WebSocketAuthorizer",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                "lambda/websocket_authorizer",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        "pip install --platform manylinux2014_x86_64 --only-binary=:all: -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                },
            ),
            timeout=Duration.seconds(30),
            memory_size=512,
            environment={
                "USER_POOL_ID": user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client_id,
                "API_KEYS_SECRET_NAME": api_keys_secret_name,
            },
            layers=[error_layer],
        )

        # Grant permissions to read from Secrets Manager
        websocket_authorizer.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{api_keys_secret_name}*"
                ],
            )
        )

        # Define the WebSocket handler Lambda function
        websocket_handler = _lambda.Function(
            self,
            "WebSocketHandler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambda/websocket"),
            timeout=Duration.seconds(15),
            memory_size=512,
            environment={
                "JOB_TABLE": job_table.table_name,
            },
            layers=[error_layer],
        )

        job_table.grant_read_write_data(websocket_handler)

        # Create WebSocket Lambda authorizer
        lambda_authorizer = authorizers.WebSocketLambdaAuthorizer(
            "WebSocketAuthorizer",
            handler=websocket_authorizer,
            identity_source=["route.request.querystring.ApiKey"],
        )

        # Create WebSocket API
        websocket_api = apigwv2.WebSocketApi(
            self,
            "WebSocketApi",
            api_name=f"{construct_id}-websocket-api",
            description="WebSocket API for real-time communication",
            route_selection_expression="$request.body.action",
        )

        self.websocket_api_id = websocket_api.api_id

        # Create separate Lambda integrations for each route
        connect_integration = integrations.WebSocketLambdaIntegration(
            "ConnectIntegration", websocket_handler
        )

        disconnect_integration = integrations.WebSocketLambdaIntegration(
            "DisconnectIntegration", websocket_handler
        )

        default_integration = integrations.WebSocketLambdaIntegration(
            "DefaultIntegration", websocket_handler
        )

        # Add routes with separate integrations
        websocket_api.add_route(
            "$connect",
            integration=connect_integration,
            authorizer=lambda_authorizer,
        )
        websocket_api.add_route(
            "$disconnect",
            integration=disconnect_integration,
        )
        websocket_api.add_route(
            "$default",
            integration=default_integration,
        )

        # Create WebSocket stage with logging
        websocket_stage = apigwv2.WebSocketStage(
            self,
            "WebSocketStage",
            web_socket_api=websocket_api,
            stage_name="prod",
            auto_deploy=True,
            throttle=apigwv2.ThrottleSettings(rate_limit=500, burst_limit=1000),
        )

        # Update Lambda environment with actual endpoint
        websocket_handler.add_environment("WEBSOCKET_ENDPOINT", websocket_stage.url)

        # Grant permissions for the Lambda to post to the WebSocket API
        websocket_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api.api_id}/*"
                ],
            )
        )

        # Outputs
        CfnOutput(
            self,
            "WebSocketApiId",
            value=websocket_api.api_id,
            description="WebSocket API ID",
        )

        CfnOutput(
            self,
            "WebSocketEndpoint",
            value=websocket_stage.url,
            description="WebSocket API endpoint",
        )

        CfnOutput(
            self,
            "WebSocketAccessLogGroup",
            value=access_log_group.log_group_name,
            description="WebSocket API Access Logs CloudWatch Log Group",
        )
