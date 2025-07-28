import time
import os
import traceback
import botocore
import boto3
import json
import logging
import sys

sys.path.append("/opt/python")  # For lambda layers

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-west-2")
dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]
JOB_TABLE = os.environ.get("JOB_TABLE", None)
CONFIG_TABLE = os.environ.get("CONFIG_TABLE", None)


def retrieve_job_info(job_id: str) -> tuple[str, str, str, str]:
    try:
        job_response = dynamodb.get_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
        )
    except Exception as e:
        logger.error(
            f"Error retrieving job info from DynamoDB: {traceback.format_exc()}"
        )
        raise Exception(f"Error retrieving job info for job: {job_id}") from e

    job_item = job_response["Item"]
    if not job_item:
        raise ValueError(f"No job found with ID: {job_id}")

    input_bucket = job_item.get("input_bucket", {}).get("S", None)
    input_key = job_item.get("input_key", {}).get("S", None)
    config_id = job_item.get("config_id", {}).get("S", None)
    institution_id = job_item.get("institution_id", {}).get("S", None)

    if (
        input_bucket is None
        or input_key is None
        or config_id is None
        or institution_id is None
    ):
        logger.error(
            f"Missing required fields in job item for job: {job_id}. "
            f"input_bucket: {input_bucket}, input_key: {input_key}, "
            f"config_id: {config_id}, institution_id: {institution_id}"
        )
        raise ValueError("Missing internal information for job")

    return (
        config_id,
        input_bucket,
        input_key,
        institution_id,
    )


def retrieve_config(config_id: str) -> dict:
    config = None
    config_response = None

    try:
        config_response = dynamodb.get_item(
            TableName=CONFIG_TABLE,
            Key={"config_id": {"S": config_id}},
        )
    except Exception as e:
        logger.error(f"Error retrieving config from DynamoDB: {traceback.format_exc()}")
        raise ValueError("Error retrieving configuration for job.") from e

    if config_response is None:
        raise ValueError(
            f"No config found for config_id: {config_id}. Was one uploaded?"
        )
    else:
        config = config_response.get("Item", {}).get("config_data", {}).get("S", None)
        if config is None:
            raise ValueError(f"No config data found for config_id: {config_id}")

        try:
            config = json.loads(config)
        except json.JSONDecodeError as e:
            logger.error(
                f"Error parsing config JSON for config_id {config_id}: {traceback.format_exc()}"
            )

            raise ValueError("Error processing configuration for job.") from e

    return config


def correct_json(json_str: str, error_message: str) -> dict:
    """
    Prompts LLM to correct the JSON string if it's not valid, using the context
    provided in the error message.
    """

    # Build the prompt for the LLM
    prompt = f"""
You are a JSON validation and correction expert.

The following JSON string is invalid:
{json_str}

The error encountered is:
{error_message}

Please correct the JSON string to make it valid. Ensure the corrected JSON adheres to the intended structure and content.
Output only the corrected JSON, without any additional text or explanation.
If the JSON can't be fixed using simple corrections (e.g., the error is not a JSON parsing error or the JSON is not recoverable), return "--" and nothing else. 
"""

    e = error_message
    for i in range(3):
        logger.warning(
            f"LLM output was not valid JSON, attempting correction {i + 1}/3: {traceback.format_exc()}"
        )

        try:
            corrected_json = invoke_bedrock_model(prompt)
            if corrected_json == "--":
                logger.error("LLM output could not be corrected, returning error.")
                return {"error": "LLM output could not be corrected."}
            else:
                results_json = json.loads(corrected_json)
                return {"output": results_json}

        except json.JSONDecodeError as next_error:
            logger.error(
                f"Error correcting JSON from LLM output: {traceback.format_exc()}. Attempt {i + 1}/3 failed."
            )
            e = next_error

    return {"error": f"Did not recover from JSON parsing error."}


def build_prompt(
    report: str,
    institution_template: dict,
    valid_values: dict,
    guidelines: list[dict] | None,
) -> str:
    """
    Builds the complete prompt for the LLM without using LangChain templates.
    """

    # Format the JSON template by escaping braces
    json_template_fixed = (
        json.dumps(institution_template, indent=4).replace("{", "{{").replace("}", "}}")
    )

    # Build the system message
    system_message = "You are an expert **pediatric** audiologist that extracts explicit hearing test data and classifies hearing loss accurately."

    # Build the human message
    human_message = f"""{report}

**Use the classification template and guidelines** to determine:
{json_template_fixed}

**Valid Values:**
```json
{json.dumps(valid_values, indent=4)}
```

**Guidelines for Classification:**
```json
{json.dumps(guidelines, indent=4)}
```

**Processing Rules (MUST Follow):**
- **Use only explicitly provided threshold values**; do not infer missing values.
- **If multiple severities are listed, assign the most severe classification.**
**Output Requirements:**
- Return classification in **EXACT JSON format** as per the template, with no modifications.
- Provide **precise reasoning** for each classification.
- Make sure there is thorough, chain of thought reasoning for each attribute's output.
- **Cite guideline numbers** when making classification decisions.
- **DO NOT include any additional explanations, assumptions, or commentary.**
- Do NOT include code block formatting (e.g., ```json or ```) in the output; output RAW JSON only.
- Be certain the JSON output is valid; braces should be balanced, etc.
"""

    # TODO: parse to regex-retrieve JSON.

    # Combine system and human messages in the format expected by Bedrock
    full_prompt = f"System: {system_message}\n\nHuman: {human_message}\n\nAssistant:"

    return full_prompt


def invoke_bedrock_model(prompt: str) -> str:
    """
    Invokes the Bedrock model directly without LangChain.
    """

    inference_profile_arn = os.environ.get("INFERENCE_PROFILE_ARN", None)
    if not inference_profile_arn:
        raise ValueError("INFERENCE_PROFILE_ARN environment variable is not set.")

    # Get inference config from environment
    inference_config = json.loads(os.environ.get("INFERENCE_CONFIG", "{}"))
    if not inference_config:
        raise ValueError(
            "INFERENCE_CONFIG environment variable is not set or is invalid JSON"
        )

    # Prepare the request body
    request_body = {
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        **inference_config,
    }

    try:
        # Invoke the model using the inference profile
        response = bedrock_runtime.invoke_model(
            modelId=inference_profile_arn,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json",
        )

        # Parse the response
        response_body = json.loads(response["body"].read())

        # Extract the generated text from the response format
        if "content" in response_body and isinstance(response_body["content"], list):
            for item in response_body["content"]:
                if item.get("type") == "text" and "text" in item:
                    return item["text"]

        # Fallback for unexpected response formats
        logger.warning(f"Unexpected response format: {response_body}")
        return str(response_body)

    except Exception as e:
        logger.error(f"Error while invoking model: {str(e)}")
        raise


def job_exists(job_id: str) -> bool:
    """
    Checks if a job with the given name already exists in DynamoDB.
    """

    try:
        response = dynamodb.get_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
        )
        return "Item" in response
    except Exception as e:
        raise ValueError(
            f"Error checking job existence: {traceback.format_exc()}"
        ) from e


def log_execution_arn(execution_arn: str, job_id: str) -> None:
    """
    Records the execution ARN for the job in DynamoDB.
    """

    try:
        print("Updating DynamoDB with execution ARN")
        dynamodb.update_item(
            TableName=JOB_TABLE,
            Key={"job_id": {"S": job_id}},
            UpdateExpression="SET execution_arn = :execution_arn",
            ExpressionAttributeValues={":execution_arn": {"S": execution_arn}},
            ConditionExpression="attribute_exists(job_id)",
            ReturnValues="UPDATED_NEW",
        )
        print("Updated dynamodb with execution ARN for job:", job_id)
    except dynamodb.exceptions.ConditionalCheckFailedException:
        raise ValueError(f"Job with ID {job_id} does not exist.")
    except Exception as e:
        logger.error(
            f"Error updating DynamoDB with execution ARN: {traceback.format_exc()}"
        )
        raise Exception("Error logging execution details for job.") from e


def categorize_diagnosis_with_lm(
    report: str,
    institution_template: dict,
    valid_values: dict,
    guidelines: list[dict] | None,
) -> dict:
    """
    Uses LLM to extract explicit facts and classify hearing loss. Either produces
    the output data JSON or None. This version doesn't use LangChain.
    """

    # Build the prompt
    prompt = build_prompt(report, institution_template, valid_values, guidelines)

    # Invoke the model
    try:
        results = invoke_bedrock_model(prompt)
    except Exception as e:
        logger.error(f"Error during LLM invocation: {traceback.format_exc()}")
        return {"error": f"LLM processor invocation failed."}

    # Parse the JSON response
    try:
        results_json = json.loads(results)
        if not isinstance(results_json, dict):
            logger.error(f"LLM output was not a valid JSON object: {results_json}")
            return {"error": "LLM output was not a valid JSON object."}
        else:
            return {"output": results_json}
    except json.JSONDecodeError as first_error:
        return correct_json(results, str(first_error))


def process_audiology_data(input_report: str, institution: str, config: dict) -> dict:
    """
    Processes the audiology data for a specific institution using the provided
    configuration. Produces either the output data JSON or the error JSON to
    be streamed over WebSocket to the client.

    Returns a dictionary with either "output" or "error" key.
    """

    institution_data = config["templates"].get(institution, {})
    institution_template = institution_data.get("template", {})
    valid_values = institution_data.get("valid_values", {})
    processing_guidelines = institution_data.get("processing_rules", {}).get(
        "rules", []
    )

    if not institution_template:
        print(f"Error: No template found for institution '{institution}'. Exiting...")
        return {"error": f"No template found for institution '{institution}'."}

    if not processing_guidelines:
        print(
            f"Warning: No processing guidelines found for '{institution}', proceeding without them."
        )
        return {"error": f"No processing guidelines found for '{institution}'."}

    # Process using the LLM without LangChain
    diagnosis_results = categorize_diagnosis_with_lm(
        report=input_report,
        institution_template=institution_template,
        valid_values=valid_values,
        guidelines=processing_guidelines,
    )  # Produces dict with either "output" or "error" key

    return diagnosis_results  # Returns either {"output": {...}} or {"error": "..."}


def retrieve_job_str(input_bucket: str, input_key: str) -> str:
    """
    Retrieves the job file from S3 and returns its content as a string.
    """
    try:
        response = s3.get_object(Bucket=input_bucket, Key=input_key)
    except Exception as e:
        logger.error(f"Error retrieving job file from S3: {e}")
        raise Exception("Error retrieving job file from S3.") from e

    try:
        body = response["Body"].read().decode("utf-8")
        return body
    except Exception as e:
        logger.error(f"Error reading job file content: {e}")
        raise Exception("Error reading job file contents.") from e


def process_job(job_id: str) -> dict:
    """
    Processes the job file data based on the input configuration, returning a
    processed record.
    """

    config_id, input_bucket, input_key, institution = retrieve_job_info(job_id)

    config = retrieve_config(config_id)

    logger.info(
        f"Record processor got job ID: {job_id} with config ID: {config_id} and input bucket: {input_bucket}, input key: {input_key}"
    )

    try:
        body = retrieve_job_str(
            input_bucket=input_bucket,
            input_key=input_key,
        )
    except Exception as e:
        return {"error": f"Error retrieving job file: {str(e)}"}

    logger.info(f"Retrieved job file content: {body[:100]}...")  # Log first 100 chars

    processing_result = process_audiology_data(
        input_report=body,
        institution=institution,
        config=config,
    )

    # TODO: on error, return error JSON out of step stage instead of passing
    # back error all the way to the client.
    return processing_result


def handler(event, context):
    """
    Maps a single patient audiology record to a classificatio JSON or error JSON.

    Returns { "statusCode": 200, "result": {...} }. "result" contains either
    {"output": {...}} or {"error": "..."}.
    """

    if JOB_TABLE is None:
        logger.error("JOB_TABLE environment variable is not set.")
        return {
            "statusCode": 500,
            "result": {"error": "Internal server error."},
            "jobId": None,
        }

    if BUCKET_NAME is None:
        logger.error("BUCKET_NAME environment variable is not set.")
        return {
            "statusCode": 500,
            "result": {"error": "Internal server error."},
            "jobId": None,
        }

    if CONFIG_TABLE is None:
        logger.error("CONFIG_TABLE environment variable is not set.")
        return {
            "statusCode": 500,
            "result": {"error": "Internal server error."},
            "jobId": None,
        }

    job_id = event.get("jobId", None)
    execution_arn = event.get("executionId", None)

    if not (job_id and execution_arn):
        logger.error("Bucket responses lanbda did not pass jobId and executionId.")
        return {
            "statusCode": 500,
            "result": {"error": "Error starting job execution."},
            "jobId": job_id,
        }

    try:
        log_execution_arn(execution_arn=execution_arn, job_id=job_id)
    except Exception as e:
        logger.error(f"Error logging execution ARN: {traceback.format_exc()}")
        return {
            "statusCode": 500,
            "result": {"error": f"Error logging execution details: {str(e)}"},
            "jobId": job_id,
        }

    try:
        processing_result = process_job(job_id=job_id)
    except Exception as e:
        logger.error(f"Error processing job {job_id}: {traceback.format_exc()}")
        return {
            "statusCode": 500,
            "result": {"error": f"Error processing job: {str(e)}"},
            "jobId": job_id,
        }

    return {
        "statusCode": 200,
        "result": processing_result,
        "jobId": job_id,
    }
