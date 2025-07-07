#!/bin/bash

read -p "Enter Cognito User Pool ID: " USER_POOL_ID
read -p "Enter new user's email address: " EMAIL
read -s -p "Enter permanent password: " PASSWORD
echo

echo "Creating user in Cognito User Pool..."

# Step 1: Create the user with only the email attribute (no username supplied)
TEMP_PASSWORD="TempPass#$(date +%s)"

CREATE_OUTPUT=$(aws cognito-idp admin-create-user \
    --username "$EMAIL" \
    --user-pool-id "$USER_POOL_ID" \
    --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
    --temporary-password "$TEMP_PASSWORD" \
    --message-action SUPPRESS \
    --output json)

if [ $? -ne 0 ]; then
    echo "Failed to create user."
    exit 1
fi

echo "User created; extracting auto-generated username..."

# Extract the auto-generated username using jq
USERNAME=$(echo "$CREATE_OUTPUT" | jq -r '.User.Username')

if [ -z "$USERNAME" ] || [ "$USERNAME" == "null" ]; then
    echo "Failed to retrieve auto-generated username."
    exit 1
fi

echo "Auto-generated username: $USERNAME"
echo "Setting permanent password..."

# Step 2: Set the permanent password using the auto-generated username
aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --permanent

if [ $? -eq 0 ]; then
    echo "Permanent password set successfully for user with username '$USERNAME' and email '$EMAIL'."
else
    echo "Failed to set permanent password."

    # Delete the user if setting the password fails
    aws cognito-idp admin-delete-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "$USERNAME"

    exit 1
fi
