#!/bin/bash

# E.g.,
# FUNCTION_NAME="AudiologyApiStack-AudiologyApiHandler80972EE0-xDFMUX6n1bIL"

if [ -z "$1" ]; then
  echo "Usage: $0 <function-name>"
  exit 1
fi

FUNCTION_NAME="$1"

aws logs tail /aws/lambda/$FUNCTION_NAME --follow
