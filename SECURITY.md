# Security

Rapport's whole point is that your recordings never leave your Mac. If you find a way they could,
that is a security issue and we want to hear about it privately first.

**Report privately:** hi@nirmaypanchal.com with "Rapport security" in the subject. You'll get a reply
within a few days. Please don't open a public issue for vulnerabilities until a fix is out.

## What's in scope

- Any path by which audio, transcripts, summaries or people data leave the machine without the user enabling a connector.
- The local API: it listens on 127.0.0.1 only and, in the desktop app, requires a per-launch token. Bypasses are in scope.
- The Voice Memos, microphone and file-system access paths.
- Supply chain: the frozen Python bundle, ffmpeg binaries and model downloads.

## Out of scope

- Issues that require an attacker to already have local code execution as the user.
- Models producing wrong transcripts or summaries.
