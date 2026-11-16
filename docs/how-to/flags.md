# Flags and revert

Feature flags are optional. The supported server is open-source Unleash, self-hosted. `gate.py flags` describes the revert path. It does not call the server, even when `UNLEASH_URL` is set, and it does not print that URL.

When a merged change needs to come back:

1. A human reverts the merge.
2. A human disables the flag on the Unleash server.

The agent does not merge, and it does not toggle a production flag.
