#!/usr/bin/env bash
# One-time: copy the three KnG secrets from Secrets Manager into SSM
# Parameter Store (standard-tier SecureString, AWS-managed aws/ssm key,
# free). Run BEFORE `terraform apply`. Idempotent; values never printed.
set -euo pipefail
export AWS_PROFILE="${AWS_PROFILE:-claude-kng}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"

for name in license-signing-private-key fastspring-api-credentials fastspring-webhook-secret; do
  value="$(aws secretsmanager get-secret-value --secret-id "kng/${name}" \
    --query SecretString --output text 2>/dev/null || true)"
  if [ -z "$value" ] || [ "$value" = "None" ]; then
    echo "skip kng/${name}: no value in Secrets Manager (set it later with aws ssm put-parameter --overwrite)"
    continue
  fi
  aws ssm put-parameter --name "/kng/${name}" --type SecureString \
    --tier Standard --overwrite --value "$value" >/dev/null
  echo "copied kng/${name} -> /kng/${name}"
done
