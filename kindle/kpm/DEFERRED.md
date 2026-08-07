# KPM package publication is deferred

The hdnext KPM client and repository format are still evolving, and Kindle
Brief has no allocated package ID or published hard-float artifact in the
canonical repository. This project therefore does not invent a KPM manifest.

The USB package installs a conventional KUAL entry and a `kindlehf` runtime
under `/mnt/us/kindle-brief`. Once a package ID and repository review exist,
the same install, launch, and uninstall hooks can be wrapped by a verified KPM
package without changing the on-device runtime.
