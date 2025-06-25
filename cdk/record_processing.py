from aws_cdk import (
    Stack,
    aws_iam as iam,
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
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.region = Stack.of(self).region
        self.account = Stack.of(self).account

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
            },
        )

        config_table.grant_read_data(record_processor_lambda)

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
            },
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

        # Passes job name and execution ID to the record processor in payload
        record_processor_task = tasks.LambdaInvoke(
            self,
            "RecordProcessorTask",
            lambda_function=record_processor_lambda,
            output_path="$.Payload",  # Pass the record processor output to the completion recorder
        )

        merge_execution_id = sfn.Pass(
            self,
            "MergeExecutionId",
            parameters={
                "executionId.$": "$$.Execution.Id",
                "recordProcessorOutput.$": "$",
            },
        )

        completion_recorder_task = tasks.LambdaInvoke(
            self,
            "CompletionRecorderTask",
            lambda_function=completion_recorder_lambda,
        )

        definition = record_processor_task.next(merge_execution_id)
        definition = definition.next(completion_recorder_task)

        self.step_function = sfn.StateMachine(
            self,
            "RecordProcessingStateMachine",
            definition=definition,
            timeout=Duration.minutes(5),
        )
