# App Replicator

Universal Android-to-Flutter mobile application cloner and reverse-engineering skill for Antigravity.

## Capabilities
- **Automated Pull & Patch**: Intercepts and patches split APKs (`apk-mitm` + `--debuggable` flag).
- **Universal Asset Extractor**: Converts Android Vector XMLs to W3C SVGs, selects highest-DPI assets, pulls Lottie animations and audio.
- **Live Screen Inspector**: Dumps screenshot + UI Automator XML hierarchy without device disk writes.
- **Flutter Synthesis**: Generates Clean Architecture Flutter projects with Cairo font typography, dark mode palettes, and Arabic RTL support.
- **Universal Frida Bypass**: Hooks Conscrypt, OkHttp3, TrustManager, and root detection.

## Invocation
```bash
/app-replicator <package_name> [--device <serial>]
```
