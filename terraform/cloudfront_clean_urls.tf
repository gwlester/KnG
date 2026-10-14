# Clean URLs: CloudFront Function that rewrites a request for an
# extensionless path (e.g. /privacy) to its real object (/privacy.html)
# before it reaches the S3 origin, so every page is reachable both with
# and without ".html". Needed so external forms that reject a ".html"
# suffix -- e.g. Google Play Console's Privacy Policy URL field -- have a
# real, working URL to use. Shared by both the live and preview
# distributions so preview always reflects live behavior.
resource "aws_cloudfront_function" "clean_urls" {
  name    = "kng-consulting-clean-urls"
  runtime = "cloudfront-js-1.0"
  comment = "Append .html to an extensionless request path"
  publish = true
  code    = <<-EOT
    function handler(event) {
      var request = event.request;
      var uri = request.uri;

      if (uri.endsWith('/')) {
        return request;
      }

      var lastSegment = uri.split('/').pop();
      if (lastSegment.indexOf('.') === -1) {
        request.uri = uri + '.html';
      }

      return request;
    }
  EOT
}
