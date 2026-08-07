# Scheduling policy

Kindle Brief deliberately installs no boot hook, cron entry, systemd unit, or
other autostart mechanism. The dashboard is launched manually from KUAL and
has a hard runtime limit. GitHub Actions schedules server-side generation;
models and providers do not schedule themselves.

When `config/base-url` is configured, each manual **Start Dashboard** launch
attempts one foreground update with a shared 20-second network budget before
starting the viewer. Network, deadline, or validation failure is non-fatal: the
dashboard continues with its last verified cache or package-bundled pages.
**Update Dashboard** remains available as a separate manual KUAL action with
longer transfer limits. Neither path creates a background service or an
unattended device schedule.
