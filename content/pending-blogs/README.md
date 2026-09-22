# Pending blogs (not published)

Articles here are written but intentionally **not** wired into the site.
`src/build_blog.py` only reads `content/blog/*.md`, so nothing in this
folder renders or deploys.

Each topic has four files, prefixed with a two-digit order number
(`NN-<slug>...`) that reflects the order the topics were requested in --
the number has no meaning outside this folder:

- `NN-<slug>.md` -- the blog post itself (front matter + body).
- `NN-<slug>-linkedin.md` -- the LinkedIn post (written as a native
  LinkedIn article/long post).
- `NN-<slug>-facebook.md` -- the Facebook teaser.
- `NN-<slug>-mewe.md` -- the MeWe teaser.

The three social files link to the post with a `{{post_url}}` placeholder
-- fill in the real URL once the post is live.

To publish one:

1. Move `NN-<slug>.md` into `content/blog/` **as `<slug>.md`**, dropping
   the `NN-` prefix (or add an explicit `slug:` front-matter field instead
   of renaming), and set a real `date:` in its front matter -- these all
   use a placeholder draft date.
2. Run `python3 src/build_blog.py` and review the rendered page.
3. Replace `{{post_url}}` in the three social files with the live URL and
   post each to its platform.
4. Delete the four files for that topic from this folder in the same
   commit.
