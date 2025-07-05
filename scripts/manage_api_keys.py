#!/usr/bin/env python3
"""
Script to manage API keys in AWS Secrets Manager for the Audiology API.
"""

import json
import boto3
import secrets
import string
import argparse
from typing import List, Dict

def generate_api_key(length: int = 32) -> str:
    """Generate a secure random API key."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def get_secret_value(secret_name: str) -> Dict:
    """Get the current secret value."""
    client = boto3.client('secretsmanager')
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return json.loads(response['SecretString'])
    except client.exceptions.ResourceNotFoundException:
        print(f"Secret {secret_name} not found. Creating new secret structure.")
        return {"api_keys": []}

def update_secret(secret_name: str, secret_data: Dict) -> None:
    """Update the secret with new data."""
    client = boto3.client('secretsmanager')
    client.update_secret(
        SecretId=secret_name,
        SecretString=json.dumps(secret_data, indent=2)
    )

def list_api_keys(secret_name: str) -> None:
    """List all API keys."""
    secret_data = get_secret_value(secret_name)
    api_keys = secret_data.get('api_keys', [])
    
    if not api_keys:
        print("No API keys found.")
        return
    
    print(f"Found {len(api_keys)} API key(s):")
    for i, key in enumerate(api_keys, 1):
        # Show only first 8 characters for security
        masked_key = key[:8] + "..." + key[-4:] if len(key) > 12 else key[:4] + "..."
        print(f"  {i}. {masked_key}")

def add_api_key(secret_name: str, api_key: str = None) -> None:
    """Add a new API key."""
    if not api_key:
        api_key = generate_api_key()
        print(f"Generated new API key: {api_key}")
    
    secret_data = get_secret_value(secret_name)
    api_keys = secret_data.get('api_keys', [])
    
    if api_key in api_keys:
        print("API key already exists!")
        return
    
    api_keys.append(api_key)
    secret_data['api_keys'] = api_keys
    
    update_secret(secret_name, secret_data)
    print(f"API key added successfully. Total keys: {len(api_keys)}")

def remove_api_key(secret_name: str, api_key: str) -> None:
    """Remove an API key."""
    secret_data = get_secret_value(secret_name)
    api_keys = secret_data.get('api_keys', [])
    
    if api_key not in api_keys:
        print("API key not found!")
        return
    
    api_keys.remove(api_key)
    secret_data['api_keys'] = api_keys
    
    update_secret(secret_name, secret_data)
    print(f"API key removed successfully. Remaining keys: {len(api_keys)}")

def main():
    parser = argparse.ArgumentParser(description='Manage API keys for Audiology API')
    parser.add_argument('--secret-name', default='audiology-api/api-keys', 
                       help='Name of the secret in Secrets Manager')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List command
    subparsers.add_parser('list', help='List all API keys')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new API key')
    add_parser.add_argument('--key', help='Specific API key to add (generates random if not provided)')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove an API key')
    remove_parser.add_argument('key', help='API key to remove')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            list_api_keys(args.secret_name)
        elif args.command == 'add':
            add_api_key(args.secret_name, args.key)
        elif args.command == 'remove':
            remove_api_key(args.secret_name, args.key)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
