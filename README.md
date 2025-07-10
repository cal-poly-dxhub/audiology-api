# audiology-api

## Prerequisites

- An AWS account
- Git
- An internet connection
- OpenSSL (for generating a Next Auth secret)

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
