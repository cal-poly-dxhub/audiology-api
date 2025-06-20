from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
)
from constructs import Construct
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_dynamodb as dynamodb


class AudiologyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.bucket = s3.Bucket(
            self,
            "AudiologyBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            public_read_access=False,
        )

        bucket_response = _lambda.Function(
            self,
            "AudiologyBucketResponses",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset("lambda/bucket_response"),
            timeout=Duration.seconds(15),
            memory_size=512,
            environment={"BUCKET_NAME": self.bucket.bucket_name},
        )

        self.audiology_table = dynamodb.Table(
            self,
            "AudiologyTable",
            partition_key=dynamodb.Attribute(
                name="id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bucket.grant_read(bucket_response)

        # Triggers for files of the form "lab_data_input/*.json"
        self.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED_PUT,
            s3n.LambdaDestination(bucket_response),
            s3.NotificationKeyFilter(prefix="lab_data_input/", suffix=".json"),
        )
