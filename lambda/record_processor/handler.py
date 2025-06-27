import time
import os
import boto3
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-west-2")
dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")

BUCKET_NAME = os.environ["BUCKET_NAME"]


def retrieve_job_info(job_name: str) -> tuple[str, str, str]:
    job_table = os.environ.get("JOB_TABLE", None)

    if not job_table:
        raise ValueError("JOB_TABLE environment variable is not set.")

    try:
        job_response = dynamodb.get_item(
            TableName=job_table,
            Key={"job_name": {"S": job_name}},
        )

        job_item = job_response.get("Item", None)
        if job_item is None:
            raise ValueError(f"No job found with name: {job_name}")

        input_bucket = job_item.get("input_bucket", {}).get("S", None)
        if input_bucket is None:
            raise ValueError(f"No input bucket found in job table for job: {job_name}")

        input_key = job_item.get("input_key", {}).get("S", None)
        if input_key is None:
            raise ValueError(f"No input key found in job table for job: {job_name}")

        config_id = job_item.get("config_id", {}).get("S", None)
        if config_id is None:
            raise ValueError(f"No config ID found in job table for job: {job_name}")

        return config_id, input_bucket, input_key

    except Exception as e:
        raise ValueError(f"Error retrieving job info: {str(e)}") from e


def retrieve_config(config_id: str) -> dict:
    config_table = os.environ.get("CONFIG_TABLE", None)

    if not config_table:
        raise ValueError("CONFIG_TABLE environment variable is not set.")

    config = None
    try:
        config_response = dynamodb.get_item(
            TableName=config_table,
            Key={"config_id": {"S": config_id}},
        )
        config = config_response.get("Item", {}).get("config_data", None).get("S", None)
    except Exception as e:
        raise ValueError(f"Error retrieving config: {str(e)}") from e

    if config is None:
        raise ValueError(f"No config found for config_id: {config_id}")
    else:
        try:
            config = json.loads(config)
        except json.JSONDecodeError as e:
            raise ValueError(f"Error parsing config JSON: {str(e)}") from e

    return config


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

    # Prepare the request body for Nova Pro
    request_body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {
            "max_new_tokens": 4096,
            "temperature": 0.0,
            "top_k": 128,
            "top_p": 0.9,
            "stopSequences": ["\n\nHuman"],
        },
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

        # Extract the generated text from Nova Pro response format
        if "output" in response_body and "message" in response_body["output"]:
            content = response_body["output"]["message"]["content"]
            if content and len(content) > 0 and "text" in content[0]:
                return content[0]["text"]

        # Fallback for different response formats
        logger.warning(f"Unexpected response format: {response_body}")
        return str(response_body)

    except Exception as e:
        logger.error(f"Error invoking Bedrock model: {str(e)}")
        raise


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
        logger.error(f"Error during LLM invocation: {str(e)}")
        return {"error": f"LLM processor invocation failed."}

    # Parse the JSON response
    try:
        results_json = json.loads(results)
        if not isinstance(results_json, dict):
            logger.error(f"LLM output was not a valid JSON object: {results_json}")
            return {"error": "LLM output was not a valid JSON object."}
        else:
            return {"output": results_json}
    except json.JSONDecodeError as e:
        logger.error(
            f"Error decoding JSON from LLM output: {str(e)}. LLM output: {results}"
        )
        return {"error": f"Unable to process record due to JSON parsing error."}


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
        body = response["Body"].read()
        return body.decode("utf-8")  # Decoding bytes to string
    except Exception as e:
        raise ValueError(f"Error retrieving job file: {str(e)}") from e


def process_job(job_name: str) -> dict:
    """
    Processes the job file data based on the input configuration, returning a
    processed record.
    """

    config_id, input_bucket, input_key = retrieve_job_info(job_name)

    config = retrieve_config(config_id)

    logger.info(
        f"Record processor got job name: {job_name} with config ID: {config_id} and input bucket: {input_bucket}, input key: {input_key}"
    )

    body = retrieve_job_str(
        input_bucket=input_bucket,
        input_key=input_key,
    )

    logger.info(f"Retrieved job file content: {body[:100]}...")  # Log first 100 chars

    processing_result = process_audiology_data(
        input_report=body,
        # TODO: pass inst. on job upload api call
        institution="Redcap",
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

    job_name = event.get("jobName")
    if not job_name:
        raise ValueError("jobName is required in the event")

    processing_result = process_job(job_name=job_name)

    return {
        "statusCode": 200,
        "result": processing_result,
        "jobName": job_name,
    }
