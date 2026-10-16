# Verification

[public-review.md](public-review.md) records the public-repository review.
Generated build reports, ELF/maps, logs and device-state checksum manifests are
local files and are ignored by Git. Earlier reports are preserved privately under
`local-backup/pre-public-cleanup/verification/`.

Run `python3 tools/check-public-repo.py` before committing. After producing a
firmware/SD release, use `python3 tools/verify-gungos-release.py` to check it.
