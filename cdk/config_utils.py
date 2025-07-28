import tomli
from typing import Dict, Any
import os


def read_model_config() -> Dict[str, Any]:
    """Read and validate the model configuration from model_config.toml"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "model_config.toml"
    )

    with open(config_path, "rb") as f:
        config = tomli.loads(f.read().decode("utf-8"))

    # Validate required sections and fields
    required_sections = ["model", "inference_config"]
    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"Missing required section '{section}' in model_config.toml"
            )

    # Validate model section
    model_section = config["model"]
    required_model_fields = {
        "inference_profile": str,
        "model_id": str,
        "model_regions": list,
    }

    for field, expected_type in required_model_fields.items():
        if field not in model_section:
            raise ValueError(f"Missing required field '{field}' in model section")
        if not isinstance(model_section[field], expected_type):
            raise ValueError(f"'{field}' must be a {expected_type.__name__}")

    # Additional validation for model_regions
    if not model_section["model_regions"]:
        raise ValueError("'model_regions' list cannot be empty")
    if not all(isinstance(region, str) for region in model_section["model_regions"]):
        raise ValueError("All items in 'model_regions' must be strings")

    # Validate inference config section
    inference_config = config["inference_config"]
    required_inference_fields = [
        "max_tokens",
        "temperature",
        "top_k",
        "top_p",
        "anthropic_version",
        "stop_sequences",
    ]
    for field in required_inference_fields:
        if field not in inference_config:
            raise ValueError(
                f"Missing required field '{field}' in inference_config section"
            )

    return config
