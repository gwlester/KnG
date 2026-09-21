# Media hosting for the training and demo videos (the Videos page).
#
# Deliberately separate from the site bucket and the live/preview distributions:
# every deploy copies www/ into releases/<sha>/ and the blue-green switch flips
# those distributions' origin path, so large video files must not live there.
# This is its own private bucket behind its own CloudFront distribution (default
# *.cloudfront.net domain for now; a custom name such as media.kng-consulting.com
# can be added later with a certificate SAN and a DNS record).
#
# Files are uploaded by hand (aws s3 sync) with versioned names, so they can be
# cached for a long time. The CORS response-headers policy below is needed so
# the caption tracks (.vtt), which browsers fetch cross-origin, can be read.

resource "aws_s3_bucket" "media" {
  bucket = var.media_bucket_name

  tags = {
    Project = "kng-consulting-site"
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "media" {
  name                              = "kng-consulting-media-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# The AWS managed "SimpleCORS" policy only added Access-Control-Allow-Origin for some
# requests: a request carrying the "Priority" header (every Chrome request does) got a
# cached response without it, so browsers refused the video and caption tracks
# ("0 seconds", nothing plays). The CORS config below has origin_override on, so it always sets them.
resource "aws_cloudfront_response_headers_policy" "media_cors" {
  name    = "kng-consulting-media-cors"
  comment = "Always send the CORS headers for the training and demo videos"

  cors_config {
    access_control_allow_credentials = false
    origin_override                  = true

    access_control_allow_headers {
      items = ["*"]
    }

    access_control_allow_methods {
      items = ["GET", "HEAD", "OPTIONS"]
    }

    access_control_allow_origins {
      items = ["*"]
    }

    access_control_expose_headers {
      items = ["Content-Length", "Content-Range", "Accept-Ranges"]
    }

    access_control_max_age_sec = 86400
  }
}

resource "aws_cloudfront_distribution" "media" {
  enabled     = true
  price_class = var.cloudfront_price_class
  comment     = "Training and demo videos"

  origin {
    domain_name              = aws_s3_bucket.media.bucket_regional_domain_name
    origin_id                = "s3-media"
    origin_access_control_id = aws_cloudfront_origin_access_control.media.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-media"
    viewer_protocol_policy = "redirect-to-https"
    compress               = false # video and captions do not benefit, and range requests must pass through

    # AWS managed "CachingOptimized" policy.
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"
    # Own policy that always adds the CORS headers (see the resource below).
    response_headers_policy_id = aws_cloudfront_response_headers_policy.media_cors.id
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Project = "kng-consulting-site"
  }
}

data "aws_iam_policy_document" "media_bucket_policy" {
  statement {
    sid       = "AllowCloudFrontOAC"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.media.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.media.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket = aws_s3_bucket.media.id
  policy = data.aws_iam_policy_document.media_bucket_policy.json
}
