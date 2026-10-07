---
platform: LinkedIn
pairs_with: 07-self-discovery-on-the-local-network.md
---

**Nobody should have to type in an IP address to connect an app to a
server on their own network.** A small UDP broadcast solves it, if you
build it right the first time.

The core idea, from a new post: a client broadcasts a small "who's out
there" packet on the local network; any server listening answers directly
back with its address. No directory service, no configuration, no DNS.

The one thing worth getting right from day one: **put a type and version
in the payload before you ship the first release.** "I am a VCM-Server,
protocol version 2" lets a future client recognize an older server (and
handle it deliberately) instead of assuming every responder speaks its
current dialect. Add that field later and every device already in the
field is running silently un-versioned, with no way to sort them out.

A few more points in the full post: time-box the listen window with a
couple of retries rather than waiting forever, prefer broadcast over
multicast unless you actually need to cross subnets, keep the broadcast
payload itself minimal since it's visible to the whole network segment,
and always keep manual entry as a fallback.

Read it here: {{post_url}}

#NetworkProtocols #SoftwareArchitecture #UDP #APIDesign
