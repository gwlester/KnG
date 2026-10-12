# secrets/

Local-dev-only key material, gitignored. Currently holds
`license_signing_private_key.pem`, the RSA private key
`src/license_signing/handler.py` signs license files with (read via
`LICENSE_SIGNING_PRIVATE_KEY_PATH`, defaulting to this directory).

This is a throwaway development keypair generated 2026-10-12. Before any
real customer-facing deployment, generate a real production keypair and
move the private half into AWS Secrets Manager -- see
`Prompts/FastSpring_implementation.md` section 4d's "Open items" note.
The matching public key is committed (not a secret) at
`../../VirtualChurchMusician/src/server/license_public_key.pem` in the
sibling repo.
