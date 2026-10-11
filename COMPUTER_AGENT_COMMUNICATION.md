# Cross-Computer Agent Communication

## Current setup (verified 2026-10-11)

Pi intercom is working between the Mac Pi session and the Desktop Project Phoenix `pi` session (`/home/blueaz/Python/project-phoenix`). A `DESKTOP-PP-ACK` round trip was confirmed.

The Desktop user service `pi-intercom-mac-forward.service` forwards the Desktop-hosted intercom broker to the Mac over SSH. The broker is not exposed on a public network listener. The Mac-side SSH key is restricted to the Desktop source address and a forced command/no-shell; the Mac's public key was not added to Desktop. Do not copy or commit private keys or host key material.

**Forwarding limitation:** OpenSSH `permitlisten` restricts TCP listen addresses/ports, not Unix-socket paths. The current reverse Unix-socket forward therefore cannot be restricted to a single socket path with `permitlisten`. SSH forwarding is configured remote-only (not local/client-to-server TCP forwarding), and the forced-command key is source-restricted. The Desktop service and both broker sockets must remain protected by their account/filesystem permissions.

If intercom stops working, check the Desktop user service and `pi-intercom status`/`pi-intercom list` on both machines. The Desktop agent can be addressed as the live `pi` session in `/home/blueaz/Python/project-phoenix`; its `subagent-chat` session is a different target.

## SSH setup principles

- SSH provides remote shell or forwarding access; it does not by itself connect Pi sessions.
- Create a dedicated Ed25519 key if needed. Never copy or commit the private key.
- Add only the public key to the target's `authorized_keys`, with the narrowest practical source and command restrictions.
- Verify host-key fingerprints through a trusted route before accepting/updating `known_hosts`.
- For this bridge, do not broaden forwarding permissions or expose a broker TCP listener without reviewing the security implications.

## Git mailbox fallback

If the bridge is unavailable, use a shared Git repository as an asynchronous mailbox under `agent-mailbox/`:

- `agent-mailbox/<sender>/YYYY-MM-DD_HHMMSS_<topic>.md` — one immutable message per file.
- Include `To`, `From`, `Date`, `Subject`, and `Reply-to` (if applicable).
- Commit and push messages; recipients fetch/pull, read, then reply in a new file referencing the original.
- Do not put credentials, private keys, or sensitive personal data in messages.
- Avoid editing or force-pushing another agent's messages. Use unique filenames to prevent conflicts.

The mailbox is asynchronous; use the verified intercom bridge for live coordination.
