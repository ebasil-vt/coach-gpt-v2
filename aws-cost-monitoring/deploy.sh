#!/bin/bash
# Deploy CoachGPT Weekly Cost Report — Lambda + SNS + EventBridge
# Runs in vt-dev account (423671285746), separate from VT AI reports
#
# Usage:
#   export AWS_PROFILE=vt-dev
#   cd aws-cost-monitoring
#   bash deploy.sh

set -euo pipefail

REGION="us-east-2"
STACK_NAME="coachgpt-cost-monitoring"
ALERT_EMAIL="ebasil@versatechinc.com"
BUDGET="20"

echo ""
echo "=== CoachGPT Cost Monitoring Deploy ==="
echo "Account: vt-dev (423671285746)"
echo "Region:  $REGION"
echo "Email:   $ALERT_EMAIL"
echo "Budget:  \$$BUDGET/month"
echo ""

# Step 1: Deploy CloudFormation stack
echo "[1/4] Deploying CloudFormation stack..."
aws cloudformation deploy \
  --template-file cloudformation-template.yaml \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    AlertEmail="$ALERT_EMAIL" \
    MonthlyBudget="$BUDGET" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region "$REGION" \
  --tags Project=coachgpt

echo "  Stack deployed."

# Step 2: Get SNS Topic ARN
SNS_TOPIC_ARN=$(aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`SNSTopicArn`].OutputValue' \
  --output text)

echo "  SNS Topic: $SNS_TOPIC_ARN"
echo ""
echo "  >>> CHECK YOUR EMAIL ($ALERT_EMAIL) and confirm the SNS subscription <<<"
echo ""

# Step 3: Upload actual Lambda code
echo "[2/4] Packaging Lambda code..."
zip -j lambda-weekly-report.zip lambda-weekly-report.py

echo "[3/4] Updating Lambda function code..."
aws lambda update-function-code \
  --function-name coachgpt-weekly-report \
  --zip-file fileb://lambda-weekly-report.zip \
  --region "$REGION"

echo "  Lambda code updated."

# Clean up zip
rm -f lambda-weekly-report.zip

# Step 4: Test
echo "[4/4] Sending test report..."
aws lambda invoke \
  --function-name coachgpt-weekly-report \
  --payload '{}' \
  --region "$REGION" \
  /tmp/coachgpt-weekly-response.json

echo ""
cat /tmp/coachgpt-weekly-response.json
echo ""
echo ""
echo "=== Deploy Complete ==="
echo ""
echo "Schedule: Every Monday 10 AM UTC (5 AM EST)"
echo "VT AI reports arrive at 9 AM UTC — CoachGPT is 1 hour later."
echo ""
echo "Check your email for the test report!"
echo ""
