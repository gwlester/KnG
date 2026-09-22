---
title: Self Discovery
date: 2026-09-22
summary: A client app finding its server on the local network shouldn't require typing in an IP address -- a small UDP broadcast, versioned from day one, does the whole job.
---

Asking a user to type in an IP address to connect an app to a server on
their own network is a rough first experience, and an unnecessary one.
Most home and church networks already give you everything needed for the
client to find the server on its own: a broadcast domain and a few
milliseconds of patience.

**Use UDP broadcast.** A client sends a small broadcast packet to the
network's broadcast address on a known port; any server listening
responds directly to the sender with its own address. No central
directory, no configuration, no DNS -- just a shout on the local network
and an answer from whatever's there to hear it. It degrades gracefully,
too: if nothing answers, the app falls back to asking for an address
manually, which is exactly where every setup used to start.

**Put a type and version in the discovery payload from day one.** The
first version of a discovery protocol is never the last. A payload that
says "I am a VCM-Server, protocol version 2" lets a newer client
recognize an older server (and behave accordingly, or say so plainly)
instead of assuming every responder speaks its own current dialect. Adding
that field after the fact means every device already in the field is
running silently un-versioned, with no way to tell them apart later.

A few points worth building around those two:

- **Time-box the listen window and retry a couple of times**, rather than
  waiting indefinitely for a reply that never arrives on a network where
  nothing is actually running the server.
- **Prefer broadcast over multicast unless you need to cross subnets.**
  Broadcast is simpler to reason about and works everywhere a flat home or
  small-office network already does; multicast adds routing and IGMP
  considerations most of these networks were never set up for.
- **Keep the broadcast payload minimal and non-sensitive.** Anything sent
  as a broadcast is visible to every device on the network segment, not
  just the intended one -- announce identity and version, not anything a
  user would consider private.
- **Let the response carry more detail than the broadcast did.** The
  broadcast only needs to say "who's out there"; the unicast reply back to
  the asking client is the right place for connection details, capability
  flags, or anything else the client actually needs to proceed.
- **Always keep manual entry as a fallback**, both for networks that block
  broadcast traffic (common on more locked-down or segmented setups) and
  for the rare case where more than one server answers and a person needs
  to pick.

The bar for "good enough" self-discovery is low: it should work
invisibly on the common case and fail obviously, not silently, on
everything else. A versioned, minimal broadcast clears that bar without
needing anything more elaborate.
