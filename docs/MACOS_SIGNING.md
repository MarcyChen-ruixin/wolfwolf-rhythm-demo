# macOS Signing and Notarization (Future)

**Current GitHub Demo status: Ad-hoc signed and not notarized.**

The v0.1.0-demo macOS builds produced by GitHub Actions use **ad-hoc**
code signing only:

```bash
codesign --force --deep --sign - "dist/Werewolf Rhythm Demo.app"
```

Ad-hoc signing is enough for local CI validation of bundle structure. It is
**not** Apple Developer ID signing and is **not** notarization.

Do not claim that an ad-hoc-signed demo is notarized.

## What this repository does today

- Builds separate native Apple Silicon (`arm64`) and Intel (`x86_64`) apps
- Performs ad-hoc signing inside `build_macos.sh`
- Verifies the signature with `codesign --verify --deep --strict`
- Uploads ZIP + SHA-256 artifacts for GitHub Releases

No Apple passwords, certificates, private keys, or notarization secrets are
stored in this repository for the initial demo workflow.

## Optional future polished release (not enabled)

A future public macOS release *may* use:

1. **Apple Developer ID Application** certificate
2. **Hardened Runtime** where required by notarization policy
3. **Apple notarization** (`notarytool`)
4. **Stapling** the notarization ticket to the `.app` or ZIP/DMG

That path is intentionally **not** wired into the current GitHub Actions
workflow. Enabling it later requires:

- A paid Apple Developer Program membership
- A Developer ID Application certificate installed as a CI secret
- An App Store Connect API key or equivalent notarization credentials
- Explicit repository maintainer approval

## Commands (documentation only — do not run without credentials)

```bash
# Example future Developer ID sign (placeholder identity)
codesign --force --deep --options runtime \
  --sign "Developer ID Application: EXAMPLE" \
  "dist/Werewolf Rhythm Demo.app"

# Example future notarization (placeholders)
xcrun notarytool submit "WerewolfRhythm-Demo-macOS-….zip" \
  --apple-id "EXAMPLE" \
  --team-id "EXAMPLE" \
  --password "EXAMPLE" \
  --wait

xcrun stapler staple "dist/Werewolf Rhythm Demo.app"
```

Replace placeholders only when real credentials are available outside git.

## Player guidance

Players downloading the current GitHub Demo should verify the ZIP came from
the official GitHub repository. macOS may show an unidentified-developer
warning. Use **System Settings → Privacy & Security → Open Anyway** only after
confirming the source. Do not disable Gatekeeper globally.
