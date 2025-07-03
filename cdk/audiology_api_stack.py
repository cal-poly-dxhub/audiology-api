from aws_cdk import RemovalPolicy, Stack, aws_s3 as s3
from constructs import Construct
from cdk.record_processing import RecordProcessing
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

        self.config_table = dynamodb.Table(
            self,
            "AudiologyConfigTable",
            partition_key=dynamodb.Attribute(
                name="config_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bucket = s3.Bucket(
            self,
            "AudiologyBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            public_read_access=False,
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.POST,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.DELETE,
                        s3.HttpMethods.HEAD,
                    ],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000,
                )
            ],
        )

        self.output_bucket = s3.Bucket(
            self,
            "AudiologyOutputBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            public_read_access=False,
        )

        self.web_socket_api = WebSocketApi(
            self,
            "WebSocketApi",
            job_table=self.audiology_table,
        )

        self.record_processing = RecordProcessing(
            self,
            "RecordProcessing",
            job_table=self.audiology_table,
            websocket_api_id=self.web_socket_api.websocket_api_id,
            config_table=self.config_table,
            bucket=self.bucket,
            output_bucket=self.output_bucket,
        )

        self.submission_api = SubmissionApi(
            self,
            "SubmissionApi",
            job_table=self.audiology_table,
            step_function=self.record_processing.step_function,
            config_table=self.config_table,
            bucket=self.bucket,
        )
