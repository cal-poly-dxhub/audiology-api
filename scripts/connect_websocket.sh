#!/bin/bash

WS_ENDPOINT=$1

wscat -c "$WS_ENDPOINT" \
  --header "Job-Name: report_sample"
