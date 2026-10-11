# Cross-Computer Agent Communication

## What works

- SSH provides remote shell access between computers; it does **not** connect their Pi sessions.
- `pi-intercom` currently discovers sessions on the same machine only. A desktop Pi session will not appear in this Mac's intercom roster.
- Until a cross-machine relay is deployed, use this repository as an asynchronous message mailbox. Use SSH for direct remote commands once authentication is configured.

## SSH setup

1. On the client computer, create an SSH key if needed (`ssh-keygen -t ed25519`). Never copy or commit the private key.
2. Add the client's **public** key (`~/.ssh/id_ed25519.pub`) to the target account's `~/.ssh/authorized_keys` using an already-authorized computer or local console.
3. Verify the target host-key fingerprint through a trusted route (for example, on the target: `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`). Only then accept/update the client's `known_hosts` entry.
4. Test: `ssh <user>@<verified-host-or-ip> 'hostname; whoami'`.

A successful SSH connection grants shell access but does not make intercom cross-machine.

## Git mailbox protocol

Use a shared Git repository both agents can access. Keep messages under `agent-mailbox/`:

- `agent-mailbox/<sender>/YYYY-MM-DD_HHMMSS_<topic>.md` — one immutable message per file.
- Include `To`, `From`, `Date`, `Subject`, and `Reply-to` (if applicable) at the top.
- Commit and push messages; recipients fetch/pull, read, then reply in a new file referencing the original message.
- Do not put credentials, private keys, or sensitive personal data in messages.
- Avoid editing or force-pushing another agent's messages. Use unique filenames to prevent conflicts.

This is asynchronous coordination, not live chat. For live cross-machine agent messaging, deploy a mutually reachable relay; do not assume local-only intercom can be made cross-machine by SSH alone.
