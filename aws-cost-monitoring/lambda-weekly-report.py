"""
CoachGPT Weekly Cost & Token Report Lambda
Sends weekly email via SNS with Bedrock usage and infrastructure costs.
Separate from VT AI weekly reports — CoachGPT has its own SNS topic, schedule, and budget.
"""

import json
import boto3
import os
from datetime import datetime, timedelta
from decimal import Decimal

ce_client = boto3.client('ce')
cloudwatch = boto3.client('cloudwatch')
sns = boto3.client('sns')

SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')
BUDGET_MONTHLY = float(os.environ.get('BUDGET_MONTHLY', '20'))
REGION = os.environ.get('AWS_REGION', 'us-east-2')

# CoachGPT uses Claude on Bedrock (not Nova)
MODELS = {
    'us.anthropic.claude-haiku-4-5-20251001-v1:0': {
        'name': 'Claude Haiku 4.5',
        'input_per_1k': 0.0008,   # $0.80/MTok
        'output_per_1k': 0.004,   # $4.00/MTok
    },
    'us.anthropic.claude-sonnet-4-6-v1:0': {
        'name': 'Claude Sonnet 4.6',
        'input_per_1k': 0.003,    # $3.00/MTok
        'output_per_1k': 0.015,   # $15.00/MTok
    },
}


def lambda_handler(event, context):
    try:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=7)

        costs = get_weekly_costs(start_date, end_date)
        tokens = get_token_usage(start_date, end_date)

        report = generate_report(costs, tokens, start_date, end_date)
        send_email(report)

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'CoachGPT weekly report sent'})
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def get_weekly_costs(start_date, end_date):
    """Get CoachGPT-tagged costs by service."""
    # Tagged costs (Project=coachgpt)
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            Filter={
                'Tags': {
                    'Key': 'Project',
                    'Values': ['coachgpt']
                }
            },
            GroupBy=[{'Type': 'DIMENSION', 'Key': 'SERVICE'}]
        )
    except Exception as e:
        print(f"Tagged cost query failed: {e}")
        return {'total': 0, 'by_service': {}}

    service_costs = {}
    total_cost = Decimal('0')

    for result in response['ResultsByTime']:
        for group in result['Groups']:
            service = group['Keys'][0]
            cost = Decimal(group['Metrics']['UnblendedCost']['Amount'])
            if service not in service_costs:
                service_costs[service] = Decimal('0')
            service_costs[service] += cost
            total_cost += cost

    # Also get Bedrock-specific cost (may not be tagged)
    try:
        bedrock_resp = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Bedrock']
                }
            }
        )
        bedrock_cost = Decimal('0')
        for result in bedrock_resp['ResultsByTime']:
            bedrock_cost += Decimal(result['Total']['UnblendedCost']['Amount'])
        if bedrock_cost > 0:
            service_costs['Amazon Bedrock (account-wide)'] = bedrock_cost
    except Exception:
        pass

    return {
        'total': float(total_cost),
        'by_service': {k: float(v) for k, v in service_costs.items()}
    }


def get_token_usage(start_date, end_date):
    """Get Bedrock token usage per model from CloudWatch."""
    start_time = datetime.combine(start_date, datetime.min.time())
    end_time = datetime.combine(end_date, datetime.min.time())

    model_usage = {}

    for model_id, model_info in MODELS.items():
        input_tokens = _get_metric(
            'InputTokenCount', model_id, start_time, end_time
        )
        output_tokens = _get_metric(
            'OutputTokenCount', model_id, start_time, end_time
        )
        invocations = _get_metric(
            'Invocations', model_id, start_time, end_time
        )

        input_cost = (input_tokens / 1000) * model_info['input_per_1k']
        output_cost = (output_tokens / 1000) * model_info['output_per_1k']

        model_usage[model_info['name']] = {
            'model_id': model_id,
            'invocations': int(invocations),
            'input_tokens': int(input_tokens),
            'output_tokens': int(output_tokens),
            'total_tokens': int(input_tokens + output_tokens),
            'input_cost': round(input_cost, 4),
            'output_cost': round(output_cost, 4),
            'total_cost': round(input_cost + output_cost, 4),
        }

    total_cost = sum(m['total_cost'] for m in model_usage.values())
    total_invocations = sum(m['invocations'] for m in model_usage.values())
    total_tokens = sum(m['total_tokens'] for m in model_usage.values())

    return {
        'models': model_usage,
        'total_cost': round(total_cost, 4),
        'total_invocations': total_invocations,
        'total_tokens': total_tokens,
    }


def _get_metric(metric_name, model_id, start_time, end_time):
    """Get a single CloudWatch Bedrock metric."""
    try:
        resp = cloudwatch.get_metric_statistics(
            Namespace='AWS/Bedrock',
            MetricName=metric_name,
            StartTime=start_time,
            EndTime=end_time,
            Period=604800,  # 1 week
            Statistics=['Sum'],
            Dimensions=[
                {'Name': 'ModelId', 'Value': model_id}
            ]
        )
        return sum(dp['Sum'] for dp in resp.get('Datapoints', []))
    except Exception:
        return 0


def generate_report(costs, tokens, start_date, end_date):
    """Generate the email report text."""
    report = f"""
COACHGPT WEEKLY COST REPORT
Period: {start_date.strftime('%b %d')} - {end_date.strftime('%b %d, %Y')}

================================================================

INFRASTRUCTURE COST (tagged: Project=coachgpt)
----------------------------------------------------------------
Total Weekly Cost: ${costs['total']:.2f}

Cost by Service:
"""

    if costs['by_service']:
        for service, cost in sorted(costs['by_service'].items(), key=lambda x: x[1], reverse=True):
            if cost > 0:
                report += f"  {service:<40} ${cost:>7.4f}\n"
    else:
        report += "  No tagged costs found. Ensure EC2 has tag Project=coachgpt.\n"

    # Token usage
    if tokens['total_invocations'] > 0:
        report += f"""

BEDROCK TOKEN USAGE
----------------------------------------------------------------
Total Invocations:  {tokens['total_invocations']:>10,} requests
Total Tokens:       {tokens['total_tokens']:>10,} tokens
Estimated Cost:     ${tokens['total_cost']:>10.4f}

Per-Model Breakdown:
"""
        for name, usage in tokens['models'].items():
            if usage['invocations'] > 0:
                avg_tokens = usage['total_tokens'] // max(usage['invocations'], 1)
                report += f"""
  {name}:
    Invocations:    {usage['invocations']:>10,}
    Input Tokens:   {usage['input_tokens']:>10,}
    Output Tokens:  {usage['output_tokens']:>10,}
    Token Cost:     ${usage['total_cost']:>10.4f}
    Avg tokens/req: {avg_tokens:>10,}
"""
    else:
        report += """

BEDROCK TOKEN USAGE
----------------------------------------------------------------
No Bedrock invocations this week.
"""

    # Projections
    weekly_total = costs['total'] + tokens['total_cost']
    monthly_proj = weekly_total * 4.3

    budget_pct = (monthly_proj / BUDGET_MONTHLY * 100) if BUDGET_MONTHLY > 0 else 0
    budget_status = "WITHIN BUDGET" if budget_pct <= 80 else "WARNING" if budget_pct <= 100 else "OVER BUDGET"

    report += f"""

PROJECTIONS
----------------------------------------------------------------
Weekly Total:       ${weekly_total:.2f}  (infra + tokens)
Monthly Projection: ${monthly_proj:.2f}
Budget:             ${BUDGET_MONTHLY:.2f}/month
Status:             {budget_status} ({budget_pct:.0f}%)

"""

    if budget_pct > 80:
        report += f"*** ALERT: Projected spend is {budget_pct:.0f}% of ${BUDGET_MONTHLY:.0f} budget ***\n\n"

    # Per-game cost estimate
    if tokens['total_invocations'] > 0:
        # A typical game uses ~12 API calls (4 ingestion + 2 analysis + 4 report + 2 research)
        games_estimate = tokens['total_invocations'] / 12
        cost_per_game = tokens['total_cost'] / max(games_estimate, 1)
        report += f"""USAGE ESTIMATE
----------------------------------------------------------------
Estimated games processed: ~{games_estimate:.0f}
Cost per game:             ~${cost_per_game:.3f}

"""

    report += f"""================================================================
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
Report: CoachGPT (separate from VT AI platform)
"""

    return report


def send_email(report):
    """Send report via SNS."""
    if SNS_TOPIC_ARN:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f'CoachGPT Weekly Report - {datetime.now().strftime("%b %d, %Y")}',
            Message=report
        )
        print("CoachGPT weekly report sent via SNS")
    else:
        print("No SNS topic configured — set SNS_TOPIC_ARN env var")
