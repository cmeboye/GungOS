# Firmware output

`sh tools/build-gungos-release.sh` writes the current development UF2 here.
Generated firmware and checksum sidecars are ignored by Git. Existing local
files may belong to earlier snapshots; source changes do not refresh them.
Distribute reviewed artifacts with their matching source revision and notices.
The existing v1.35 tag remains a separate device-test release.
