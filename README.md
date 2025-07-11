# audiology-api

## Prerequisites

- An AWS account
- Git
- An internet connection
- OpenSSL (for generating a Next Auth secret)

## System Design

1. Authorizer Lambda:
   - Handles authentication for API Gateway
   - Checks for JSON Web Token (JWT) from Cognito
   - Checks for API key if JWT is not present
   - Returns a policy document defining user permissions

2. API Lambda:
   - Handles API Gateway requests
   - Contains two main handlers:
     a. Upload Config Handler: Processes configuration uploads
     b. Upload Handler: Handles file uploads, creates jobs, and returns pre-signed URLs

3. Record Processor Lambda:
   - Contains prompts for processing the uploaded data
   - Triggered by a step function

4. Bucket Response Lambda:
   - Triggered by S3 put operations
   - Initiates the step function that triggers the Record Processor Lambda

5. Completion Lambda:
   - Handles the completion of the job processing

6. WebSocket Lambda:
   - Manages WebSocket connections
   - Uses job IDs to connect clients to the appropriate WebSocket route

Overall design flow:
1. User authenticates through API Gateway, which uses the Authorizer Lambda
2. User uploads a configuration using the API Lambda's Upload Config Handler
3. User initiates a job using the API Lambda's Upload Handler, receiving a pre-signed URL and job ID
4. User uploads the file to S3 using the pre-signed URL
5. Bucket Response Lambda triggers a step function
6. Step function initiates the Record Processor Lambda
7. Processing completes, and the Completion Lambda is invoked
8. User can connect to a WebSocket using the job ID to receive updates


## API Testing Scripts

- `scripts/test_config_upload.sh` uploads a configuration from a JSON file.

  ```
  bash scripts/test_config_upload.sh config/config.json TestConfig
  ```

- `scripts/test_socket_chain.sh` demonstrates uploading a record and getting a response.

  ```
  bash scripts/test_socket_chain.sh <File containing single record>
  ```

Both of these involve variables that need to be set (e.g., API endpoints). They also look for the `AUDIOLOGY_API_KEY` environment variable. Either set this to a value in Secrets Manager or see below for instructions for creating a new key.

## Backend Deployment

This project is deployed on AWS using the Cloud Development Kit (CDK). The deployment process is as follows:

- Clone the repository:

  ```bash
    git clone https://github.com/cal-poly-dxhub/audiology-api
    cd audiology-api
  ```

- Install `uv`:

  ```
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

- Sync the deployment modules and activate the virtual environment. This installs required Python packages.

  ```
  uv sync --only-group deployment && source .venv/bin/activate
  ```

- Deploy:

  ```
  cdk deploy
  ```

- Check that your account has enabled necessary Bedrock models. You can do this by following the steps under "Request access to an Amazon Bedrock foundation model" [here](https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html#getting-started-model-access) for Nova Pro. This step may not be necessary.

- After completing deployment, use the API key configuration script to create an API key for calls. Use `ApiKeysSecretName` from the CloudFormation output:

  ```bash
  python scripts/manage_api_key.py add --secret-name <value of ApiKeysSecretName>
  ```

## Local Frontend Deployment

This project is not configured to deploy a frontend on AWS yet. However, you can run the local frontend development server by following these steps:

- Install `bun`

  ```bash
  curl -fsSL https://bun.sh/install | bash
  ```

- Generate a cryptographically secure Next Auth secret using OpenSSL:

  ```bash
  openssl rand -base64 32
  ```

- Create the file `frontend/.env.local` with the following environment variables:

  ```env
  # Find these variables in the CloudFormation output after deploying the backend
  NEXT_PUBLIC_JOB_ENDPOINT=<value of SubmissionApiAudiologyApiEndpoint>
  NEXT_PUBLIC_WS_ENDPOINT=<value of WebSocketApiWebSocketEndpoint>
  NEXT_PUBLIC_COGNITO_USER_POOL_ID=<value of UserPoolId>
  COGNITO_CLIENT_ID=<value of UserPoolClientId>

  # From the OpenSSL command above
  NEXTAUTH_SECRET=<value generated from OpenSSL>

  # Pick a port. 3000 is a common default.
  NEXTAUTH_URL=http://localhost:<port> # e.g., http://localhost:3000
  ```

- Deploy the frontend:

  ```bash
  cd frontend && bun install && bun dev --port <port>
  ```

- Create a user with the create_user script: `bash scripts/create_user.sh`

- Log in to the frontend at `http://localhost:<port>` using the credentials you created for your first user.
