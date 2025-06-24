from aws_cdk import (
    Stack,
)
from constructs import Construct
from cdk.submission_api import SubmissionApi
from cdk.web_socket_api import WebSocketApi


class AudiologyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.submission_api = SubmissionApi(
            self,
            "SubmissionApi",
        )

        self.web_socket_api = WebSocketApi(
            self,
            "WebSocketApi",
            job_table_name=self.submission_api.job_table_name,
        )
