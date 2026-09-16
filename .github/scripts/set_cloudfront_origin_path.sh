#!/usr/bin/env bash
# Flip a CloudFront distribution's origin[0].origin_path. Used by
# deploy-to-aws.yml (build-and-upload's preview flip, switch-live) and
# rollback.yml -- the one piece of blue-green switch logic shared by all
# three, kept in one place instead of copy-pasted three times.
#
# Usage: set_cloudfront_origin_path.sh <distribution-id> <new-origin-path>
# Prints the distribution's previous origin_path to stdout (an empty line
# if it was never set) -- callers that care about "what was live before"
# (switch-live's retention cleanup) capture this; callers that don't
# (rollback, the preview flip) just discard it.
set -euo pipefail

dist_id="$1"
new_path="$2"

config_file="$(mktemp)"
new_config_file="$(mktemp)"
trap 'rm -f "${config_file}" "${new_config_file}"' EXIT

aws cloudfront get-distribution-config --id "${dist_id}" > "${config_file}"
etag="$(jq -r '.ETag' "${config_file}")"
old_path="$(jq -r '.DistributionConfig.Origins.Items[0].OriginPath' "${config_file}")"

jq --arg path "${new_path}" \
  '.DistributionConfig.Origins.Items[0].OriginPath = $path' "${config_file}" \
  | jq '.DistributionConfig' > "${new_config_file}"

aws cloudfront update-distribution \
  --id "${dist_id}" \
  --if-match "${etag}" \
  --distribution-config "file://${new_config_file}" \
  > /dev/null

echo "${old_path}"
