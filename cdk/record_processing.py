from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
from aws_cdk import Duration
from .config_utils import read_model_config
import json


class RecordProcessing(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        job_table: dynamodb.Table,
        websocket_api_id: str,
        config_table: dynamodb.Table,
        bucket: s3.Bucket,
        output_bucket: s3.Bucket,
        error_layer: _lambda.LayerVersion,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.region = Stack.of(self).region
        self.account = Stack.of(self).account

        # Read model configuration
        model_config = read_model_config()

        print("Model configuration loaded successfully: ", model_config)

        inference_profile = model_config["model"]["inference_profile"]
        model_id = model_config["model"]["model_id"]
        model_regions = model_config["model"]["model_regions"]

        inference_profile_arn = f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{inference_profile}"
        foundation_model_arns = [
            f"arn:aws:bedrock:{region}::foundation-model/{model_id}"
            for region in model_regions
        ]

        record_processor_lambda = _lambda.Function(
            self,
            "AudiologyRecordProcessor",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                "lambda/record_processor",
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
                "JOB_TABLE": job_table.table_name,
                "CONFIG_TABLE": config_table.table_name,
                "INFERENCE_PROFILE_ARN": inference_profile_arn,
                "BUCKET_NAME": bucket.bucket_name,
                "INFERENCE_CONFIG": json.dumps(model_config["inference_config"]),
            },
            layers=[error_layer],
        )

        job_table.grant_read_write_data(record_processor_lambda)
        bucket.grant_read(record_processor_lambda)
        config_table.grant_read_data(record_processor_lambda)
        record_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=foundation_model_arns + [inference_profile_arn],
            )
        )

        completion_recorder_lambda = _lambda.Function(
            self,
            "AudiologyCompletionRecorder",
            runtime=_lambda.Runtime.PYTHON_3_13,
            handler="handler.handler",
            code=_lambda.Code.from_asset(
                "lambda/completion_recorder",
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
                "JOB_TABLE": job_table.table_name,
                "OUTPUT_BUCKET_NAME": output_bucket.bucket_name,
            },
            layers=[error_layer],
        )

        job_table.grant_read_write_data(record_processor_lambda)
        job_table.grant_read_write_data(completion_recorder_lambda)

        completion_recorder_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[
                    f"arn:aws:execute-api:{self.region}:{self.account}:{websocket_api_id}/*"
                ],
            )
        )

        # Adds the execution ID to the payload for the record processor
        prep_payload = sfn.Pass(
            self,
            "PrepareStepPayload",
            parameters={
                "jobId.$": "$.jobId",
                "executionId.$": "$$.Execution.Id",
            },
        )

        # Passes job name and execution ID to the record processor in payload
        record_processor_task = tasks.LambdaInvoke(
            self,
            "RecordProcessorTask",
            lambda_function=record_processor_lambda,
            output_path="$.Payload",  # Pass the record processor output to the completion recorder
        )

        completion_recorder_task = tasks.LambdaInvoke(
            self,
            "CompletionRecorderTask",
            lambda_function=completion_recorder_lambda,
        )

        output_bucket.grant_put(completion_recorder_lambda)

        definition = prep_payload.next(record_processor_task)
        definition = definition.next(completion_recorder_task)

        self.step_function = sfn.StateMachine(
            self,
            "RecordProcessingStateMachine",
            definition=definition,
            timeout=Duration.minutes(5),
        )
