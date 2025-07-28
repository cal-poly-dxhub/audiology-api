from aws_cdk import RemovalPolicy, Stack, aws_s3 as s3
from constructs import Construct
from aws_cdk import CfnOutput
from cdk.record_processing import RecordProcessing
from cdk.submission_api import SubmissionApi
from cdk.web_socket_api import WebSocketApi
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_secretsmanager as secretsmanager


class AudiologyApiStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.error_layer = _lambda.LayerVersion(
            self,
            "AudiologyErrorLayer",
            code=_lambda.Code.from_asset("lambda/layers/audiology_errors"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_13],
            description="Layer for Audiology API error handling",
        )

        # Create Cognito User Pool at the top of the stack
        self.user_pool = cognito.UserPool(
            self,
            "AudiologyUserPool",
            user_pool_name="audiology-user-pool",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(email=True, username=False),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create User Pool Client
        self.user_pool_client = cognito.UserPoolClient(
            self,
            "AudiologyUserPoolClient",
            user_pool=self.user_pool,
            user_pool_client_name="audiology-client",
            auth_flows=cognito.AuthFlow(
                user_password=True, user_srp=True, admin_user_password=True
            ),
            generate_secret=False,
            prevent_user_existence_errors=True,
        )

        # Create API Keys Secret
        self.api_keys_secret = secretsmanager.Secret(
            self,
            "AudiologyApiKeysSecret",
            secret_name="audiology-api-keys",
            description="API keys for Audiology API authentication",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"api_keys": []}',
                generate_string_key="placeholder",
                exclude_characters="",
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.audiology_table = dynamodb.Table(
            self,
            "AudiologyJobTable",
            partition_key=dynamodb.Attribute(
                name="job_id", type=dynamodb.AttributeType.STRING
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
            error_layer=self.error_layer,
            user_pool_id=self.user_pool.user_pool_id,
            user_pool_client_id=self.user_pool_client.user_pool_client_id,
            api_keys_secret_name=self.api_keys_secret.secret_name,
        )

        self.record_processing = RecordProcessing(
            self,
            "RecordProcessing",
            job_table=self.audiology_table,
            websocket_api_id=self.web_socket_api.websocket_api_id,
            config_table=self.config_table,
            bucket=self.bucket,
            output_bucket=self.output_bucket,
            error_layer=self.error_layer,
        )

        self.submission_api = SubmissionApi(
            self,
            "SubmissionApi",
            job_table=self.audiology_table,
            step_function=self.record_processing.step_function,
            config_table=self.config_table,
            bucket=self.bucket,
            user_pool=self.user_pool,
            user_pool_client=self.user_pool_client,
            error_layer=self.error_layer,
            api_keys_secret=self.api_keys_secret,
        )

        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self,
            "ApiKeysSecretName",
            value=self.api_keys_secret.secret_name,
            description="Name of the Secrets Manager secret containing API keys",
        )
