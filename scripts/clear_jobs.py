import boto3
import sys


def clear_dynamodb_table(table_name, region_name="us-west-2"):
    # Initialize the DynamoDB client
    dynamodb_client = boto3.client("dynamodb", region_name=region_name)

    # Scan the table to get all items
    response = dynamodb_client.scan(TableName=table_name)
    items = response.get("Items", [])

    # Delete each item
    for item in items:
        key = {
            k: v
            for k, v in item.items()
            if k
            in [
                key["AttributeName"]
                for key in dynamodb_client.describe_table(TableName=table_name)[
                    "Table"
                ]["KeySchema"]
            ]
        }
        dynamodb_client.delete_item(TableName=table_name, Key=key)

    print(f"Cleared all items from table: {table_name}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clear_jobs.py <table_name>")
        sys.exit(1)

    table_name = sys.argv[1]
    clear_dynamodb_table(table_name)
