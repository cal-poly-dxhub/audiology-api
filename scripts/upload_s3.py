import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError

def upload_file_to_s3(file_path: str, bucket_name: str, key: str):
    """
    Just uploads a file to S3.
    """
    s3 = boto3.client('s3')

    try:
        s3.upload_file(file_path, bucket_name, key)
        print(f"File '{file_path}' uploaded to bucket '{bucket_name}' with key '{key}'.")
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except NoCredentialsError:
        print("Error: No AWS credentials found.")
    except PartialCredentialsError:
        print("Error: Incomplete AWS credentials configuration.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    file_path = "/Users/spandan/Projects/dxhub/audiology-api/scripts/dummy_json.json"
    bucket_name = "audiologyapistack-audiologybucket1df9aa41-6pad9bmyikok"
    key = "lab_data_input/dummy_json.json"

    upload_file_to_s3(file_path, bucket_name, key)
