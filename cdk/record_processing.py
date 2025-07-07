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

        regions = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
        ]

        inference_profiles = [
            f"arn:aws:bedrock:{region}:{self.account}:inference-profile/us.amazon.nova-pro-v1:0"
            for region in regions
        ]

        model_arns = [
            f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-pro-v1:0"
            for region in regions
        ]

        main_inference_profile = f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/us.amazon.nova-pro-v1:0"

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
                "INFERENCE_PROFILE_ARN": main_inference_profile,
                "BUCKET_NAME": bucket.bucket_name,
            },
            layers=[error_layer],
        )

        job_table.grant_read_write_data(record_processor_lambda)
        bucket.grant_read(record_processor_lambda)
        config_table.grant_read_data(record_processor_lambda)
        record_processor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=model_arns + inference_profiles,
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
                "jobName.$": "$.jobName",
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
