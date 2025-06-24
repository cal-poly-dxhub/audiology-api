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
from aws_cdk import aws_apigateway as apigateway


POWERTOOLS_LAYER_VERSION_ARN = "arn:aws:lambda:us-west-2:017000801446:layer:AWSLambdaPowertoolsPythonV3-python39-x86_64:18"


class SubmissionApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        job_table: dynamodb.Table,
        **kwargs,
    ) -> None:
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
            code=_lambda.Code.from_asset(
                "lambda/bucket_response",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                },
            ),
            timeout=Duration.seconds(15),
            memory_size=512,
            environment={
                "BUCKET_NAME": self.bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
            },
        )

        self.bucket.grant_read(bucket_response)

        job_table.grant_read_write_data(bucket_response)

        # Triggers for files of the form "input_reports/*.csv"
        self.bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED_PUT,
            s3n.LambdaDestination(bucket_response),
            s3.NotificationKeyFilter(prefix="input_reports/", suffix=".csv"),
        )

        self.powertools_layer = _lambda.LayerVersion.from_layer_version_arn(
            self,
            "PowertoolsLayer",
            layer_version_arn=POWERTOOLS_LAYER_VERSION_ARN,
        )

        self.api_handler = _lambda.Function(
            self,
            "AudiologyApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                "lambda/api",
                bundling={
                    "image": _lambda.Runtime.PYTHON_3_13.bundling_image,
                    "command": [
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -au . /asset-output",
                    ],
                },
            ),
            timeout=Duration.seconds(15),
            memory_size=512,
            environment={
                "BUCKET_NAME": self.bucket.bucket_name,
                "TABLE_NAME": job_table.table_name,
            },
            layers=[self.powertools_layer],
        )

        self.bucket.grant_put(self.api_handler)

        self.api = apigateway.RestApi(
            self,
            "AudiologyApi",
            rest_api_name="Audiology API",
            description="File upload and job update API for the Audiology project.",
        )

        upload_resource = self.api.root.add_resource("upload")
        upload_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.api_handler),
            # TODO: possibly define responses with method_responses
        )
