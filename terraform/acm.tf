# DNS lives at GoDaddy, not Route53, so validation can't be automated end to
# end: `terraform apply -target=aws_acm_certificate.site` first, add the
# CNAME records from the `dns_records_to_add_at_godaddy` output at GoDaddy,
# then run a full `terraform apply`. See terraform/README.md.

resource "aws_acm_certificate" "site" {
  provider = aws.us_east_1

  domain_name               = var.live_domain_names[0]
  subject_alternative_names = concat(slice(var.live_domain_names, 1, length(var.live_domain_names)), [var.preview_domain_name])
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate_validation" "site" {
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.site.arn
  validation_record_fqdns = [for o in aws_acm_certificate.site.domain_validation_options : o.resource_record_name]
}
