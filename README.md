# Collaboration
Thanks for your interest in our solution.  Having specific examples of replication and cloning allows us to continue to grow and scale our work. If you clone or download this repository, kindly shoot us a quick email to let us know you are interested in this work!

[wwps-cic@amazon.com] 

# Disclaimers

**Customers are responsible for making their own independent assessment of the information in this document.**

**This document:**

(a) is for informational purposes only, 

(b) represents current AWS product offerings and practices, which are subject to change without notice, and 

(c) does not create any commitments or assurances from AWS and its affiliates, suppliers or licensors. AWS products or services are provided “as is” without warranties, representations, or conditions of any kind, whether express or implied. The responsibilities and liabilities of AWS to its customers are controlled by AWS agreements, and this document is not part of, nor does it modify, any agreement between AWS and its customers. 

(d) is not to be considered a recommendation or viewpoint of AWS

**Additionally, all prototype code and associated assets should be considered:**

(a) as-is and without warranties

(b) not suitable for production environments

(d) to include shortcuts in order to support rapid prototyping such as, but not limitted to, relaxed authentication and authorization and a lack of strict adherence to security best practices

**All work produced is open source. More information can be found in the GitHub repo.**

## Authors
- Spandan Jignesh Suthar sjsuthar@calpoly.edu

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
   - Handles the completion of the job processing by reporting results over WebSocket and marking the job as complete in job records

6. WebSocket Lambda:
   - Manages WebSocket connections, responding to `$connect`, `$disconnect`, and `$default`
   - Uses job IDs to connect clients to the appropriate WebSocket stream

Overall design flow:
1. User authenticates through API Gateway, which uses the Authorizer Lambda
2. User uploads a configuration using the API Lambda's Upload Config Handler
3. User initiates a job using the API Lambda's Upload Handler, receiving a pre-signed URL and job ID
4. User uploads the file to S3 using the pre-signed URL
5. Bucket Response Lambda triggers a step function, and the user can connect to WebSocket to listen to job events
6. Step function initiates the Record Processor Lambda
7. Processing completes, and the Completion Lambda is invoked
8. User receives completion updates over WebSocket connection

<img width="2137" height="1822" alt="Audiology API Architecture" src="https://github.com/user-attachments/assets/62893d04-edc9-464e-ad70-9359d4bef0b4" />


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
