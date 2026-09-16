# Preview distribution: always serves whatever build-and-upload most
# recently uploaded to releases/<sha>/, ahead of switch-live promoting it
# to the live distribution -- lets a human smoke-test the real deployed
# output (over real HTTPS, through real CloudFront) before approving the
# switch. See Prompts/ToDo.md's "Blue-Green Deployments" item.
#
# Shares the OAC and S3 bucket policy with the live distribution, and a SAN
# on the same ACM certificate, but is a fully separate distribution/alias --
# CloudFront requires each alias to belong to exactly one distribution, so
# preview_domain_name can never also appear in the live distribution's
# aliases.

resource "aws_cloudfront_distribution" "preview" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  aliases             = [var.preview_domain_name]

  origin {
    domain_name              = aws_s3_bucket.site.bucket_regional_domain_name
    origin_id                = "s3-site"
    origin_access_control_id = aws_cloudfront_origin_access_control.site.id

    # Unlike the live distribution, origin_path here is flipped by
    # build-and-upload on every deploy (not switch-live), automatically, no
    # approval needed -- it never serves anything other people rely on.
    # Still ignore_changes'd for the same reason as the live distribution.
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

    # AWS managed "CachingDisabled" -- every request goes to the S3 origin,
    # trading cache efficiency (irrelevant at preview's traffic level) for
    # a guarantee the reviewer always sees the exact release just uploaded,
    # with no invalidation step needed after each origin_path flip.
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
  }

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
    Purpose = "preview"
  }
}
