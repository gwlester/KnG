---
platform: MeWe
pairs_with: 07-self-discovery-on-the-local-network.md
---

For anyone building client/server apps for home or local networks: UDP
broadcast discovery is simpler than it sounds, and the one thing to get
right up front is a type+version field in the payload -- retrofitting it
later means every deployed device is stuck un-versioned. Wrote up the
approach.

{{post_url}}
