# Scheduling policy

Kindle Brief deliberately installs no boot hook, cron entry, systemd unit, or
other autostart mechanism. The dashboard is launched manually from KUAL and
has a hard runtime limit. Server-side generation is scheduled independently;
the Kindle-side cache changes only when the user selects **Update Dashboard**.
