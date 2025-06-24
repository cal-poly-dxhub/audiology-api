from aws_cdk import RemovalPolicy, Stack
from constructs import Construct
from cdk.submission_api import SubmissionApi
from cdk.web_socket_api import WebSocketApi
from aws_cdk import aws_dynamodb as dynamodb


class AudiologyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.audiology_table = dynamodb.Table(
            self,
            "AudiologyJobTable",
            partition_key=dynamodb.Attribute(
                name="job_name", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.submission_api = SubmissionApi(
            self,
            "SubmissionApi",
            job_table=self.audiology_table,
        )

        self.web_socket_api = WebSocketApi(
            self,
            "WebSocketApi",
            job_table=self.audiology_table,
        )
