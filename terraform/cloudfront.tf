resource "aws_cloudfront_origin_access_control" "site" {
  name                              = "kng-consulting-site-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "site" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  aliases             = var.live_domain_names

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id

    # Blue-green: origin_path selects which releases/<sha>/ prefix is
    # "live" and is flipped by deploy-to-aws.yml's switch-live job via
    # `aws cloudfront update-distribution`, not by Terraform -- deliberately
    # decided in Prompts/ToDo.md's "Blue-Green Deployments" item so CLI
    # switches/rollbacks never fight a `terraform apply` trying to reset it.
    # The value below only matters for the very first `terraform apply`
    # (before any release has ever been uploaded); ignore_changes below
    # means Terraform never touches this origin block again afterward --
    # including origin_access_control_id/domain_name, so a bucket or OAC
    # replacement needs the ignore_changes line removed for that one apply.
    origin_path = ""
  }

  lifecycle {
    ignore_changes = [origin]
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-site"
    viewer_protocol_policy = "redirect-to-https"

    # AWS managed "CachingOptimized" policy -- long cache, no cookies/query
    # strings forwarded, appropriate for a static site.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
  }

  # index.html is served for a missing path too, since this is a single
  # small static site rather than one with a real 404 page yet.
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = aws_acm_certificate_validation.site.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Project = "kng-consulting-site"
  }
}
