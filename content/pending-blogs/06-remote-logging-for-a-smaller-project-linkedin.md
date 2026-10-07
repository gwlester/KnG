---
platform: LinkedIn
pairs_with: 06-remote-logging-for-a-smaller-project.md
---

**Remote logging doesn't require an observability platform. It requires
being honest with users about what it sends and when.**

Most remote logging advice assumes an ELK stack and an ops team. A small
project -- a desktop app, a handful of users, no dedicated infra -- needs
something much smaller, and something that doesn't quietly become
telemetry nobody agreed to.

What I've landed on, from a new post:

- Opt-in, explicitly, every time -- especially for a product whose promise
  is that it works air-gapped by default. Silent, always-on log shipping
  breaks that promise.
- Structured logs from the start (JSON, not free text) -- barely more
  effort to write, and the difference between grepping and actually
  querying once there's more than a couple of files.
- A correlation ID across client and server, so one user action becomes
  one traceable thread instead of "somewhere in these three log files."
- A destination and retention window sized to the project -- a bucket you
  already control, not a platform priced for volumes you'll never hit.
- A hard rule that logs record what failed, never the user data involved.

The goal isn't observability as a discipline -- it's being able to help
the one user who hit the one bug, without asking everyone else to trust
you with more than they signed up for.

Full post: {{post_url}}

#SoftwareEngineering #Logging #Observability #SmallTeams #Privacy
