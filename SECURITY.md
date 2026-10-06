# Security

Do not include auth keys, Supervisor tokens, node state files or full backups in
issues. The dashboard's diagnostic report excludes credentials but contains
network names and addresses.

Report non-sensitive bugs through GitHub issues. For vulnerabilities, use GitHub
private vulnerability reporting if enabled; otherwise ask for a private reporting
channel without posting exploit details or credentials.

The add-on runs on the host network with capabilities and mounts required by its
networking and file-sharing features. File shares and Funnel are disabled by
default. Maintain Home Assistant, this add-on, and its base/Tailscale dependencies.

All upstream-derived code retains its MIT license and attribution; see NOTICE.md.
