output "s3_bucket_name" {
  description = "Set this as the S3_BUCKET_NAME GitHub repo variable."
  value       = aws_s3_bucket.site.bucket
}

output "cloudfront_distribution_id" {
  description = "Set this as the CLOUDFRONT_DISTRIBUTION_ID GitHub repo variable."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  description = "The distribution's own *.cloudfront.net domain -- the CNAME target for every alias at GoDaddy."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "github_actions_deploy_role_arn" {
  description = "Set this as the AWS_DEPLOY_ROLE_ARN GitHub repo variable."
  value       = aws_iam_role.github_actions_deploy.arn
}

output "dns_records_to_add_at_godaddy" {
  description = "Every DNS record to create at GoDaddy for this site."
  value = concat(
    [
      for o in aws_acm_certificate.site.domain_validation_options : {
        purpose = "ACM certificate validation"
        type    = o.resource_record_type
        name    = o.resource_record_name
        value   = o.resource_record_value
      }
    ],
    [
      for d in slice(var.domain_names, 1, length(var.domain_names)) : {
        purpose = "CNAME to CloudFront"
        type    = "CNAME"
        name    = d
        value   = aws_cloudfront_distribution.site.domain_name
      } if startswith(d, "www.")
    ]
  )
}
