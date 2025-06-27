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
from aws_cdk import aws_stepfunctions as stepfunctions


POWERTOOLS_LAYER_VERSION_ARN = "arn:aws:lambda:us-west-2:017000801446:layer:AWSLambdaPowertoolsPythonV3-python39-x86_64:18"


class SubmissionApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        job_table: dynamodb.Table,
        step_function: stepfunctions.StateMachine,
        config_table: dynamodb.Table,
        bucket: s3.Bucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

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
                "BUCKET_NAME": bucket.bucket_name,
                "JOB_TABLE": job_table.table_name,
                "STEP_FUNCTION_ARN": step_function.state_machine_arn,
            },
        )

        bucket.grant_read(bucket_response)
        step_function.grant_start_execution(bucket_response)

        job_table.grant_read_write_data(bucket_response)

        # Triggers for files of the form "input_reports/*.csv"
        bucket.add_event_notification(
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
                "BUCKET_NAME": bucket.bucket_name,
                "TABLE_NAME": job_table.table_name,
                "JOB_TABLE": job_table.table_name,
                "CONFIG_TABLE_NAME": config_table.table_name,
            },
            layers=[self.powertools_layer],
        )

        config_table.grant_read_write_data(self.api_handler)
        bucket.grant_put(self.api_handler)
        job_table.grant_read_write_data(self.api_handler)

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

        upload_config_resource = self.api.root.add_resource("upload_config")
        upload_config_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.api_handler),
        )
