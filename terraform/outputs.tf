output "s3_bucket_name" {
  description = "Set this as the S3_BUCKET_NAME GitHub repo variable."
  value       = aws_s3_bucket.site.bucket
}

output "cloudfront_distribution_id" {
  description = "Set this as the CLOUDFRONT_DISTRIBUTION_ID GitHub repo variable."
  value       = aws_cloudfront_distribution.site.id
}

output "cloudfront_domain_name" {
  description = "The live distribution's own *.cloudfront.net domain -- the CNAME target for its aliases at GoDaddy."
  value       = aws_cloudfront_distribution.site.domain_name
}

output "preview_cloudfront_distribution_id" {
  description = "Set this as the PREVIEW_CLOUDFRONT_DISTRIBUTION_ID GitHub repo variable."
  value       = aws_cloudfront_distribution.preview.id
}

output "preview_cloudfront_domain_name" {
  description = "The preview distribution's own *.cloudfront.net domain -- the CNAME target for preview_domain_name at GoDaddy."
  value       = aws_cloudfront_distribution.preview.domain_name
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
      for d in slice(var.live_domain_names, 1, length(var.live_domain_names)) : {
        purpose = "CNAME to CloudFront (live)"
        type    = "CNAME"
        name    = d
        value   = aws_cloudfront_distribution.site.domain_name
      } if startswith(d, "www.")
    ],
    [
      {
        purpose = "CNAME to CloudFront (preview)"
        type    = "CNAME"
        name    = var.preview_domain_name
        value   = aws_cloudfront_distribution.preview.domain_name
      }
    ],
    [
      for t in aws_sesv2_email_identity.contact_domain.dkim_signing_attributes[0].tokens : {
        purpose = "SES DKIM (contact form email)"
        type    = "CNAME"
        name    = "${t}._domainkey.${local.contact_domain}"
        value   = "${t}.dkim.amazonses.com"
      }
    ]
  )
}

output "contact_function_url" {
  description = "The contact form's endpoint -- paste into the form's data-endpoint attribute in www/contact.html."
  value       = aws_lambda_function_url.contact.function_url
}
