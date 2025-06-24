from aws_cdk import (
    Stack,
)
from constructs import Construct
from cdk.api_stack import ApiStack
from cdk.ws_stack import WebSocketApiStack


class AudiologyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.api_stack = ApiStack(
            self,
            "ApiStack",
            env=kwargs.get("env"),
        )

        self.ws_stack = WebSocketApiStack(
            self,
            "WebSocketApiStack",
            env=kwargs.get("env"),
        )
