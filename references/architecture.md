# App Replicator v2.0 — Architectural Pipeline

```
Phase 0: Discovery
  ADB Discovery → Package verification → Environment check
        │
Phase 1: Recon & Patching
  Split APK Pull → apk-mitm SSL bypass + --debuggable → Reinstall
        │
Phase 2: Asset Extraction
  Vector Drawable XMLs → Standard W3C SVGs
  Density Selection (xxxhdpi > xxhdpi > xhdpi)
  SVG Opacity Scan → Auto-convert to white PNG if opacity < 0.5
  Raw Media (MP3/WAV/OGG) & Lottie (JSON)
        │
Phase 2.5: Design System
  Fonts (.otf/.ttf) → pubspec.yaml → Hot-restart verify
  ARSC Tokens → Named color constants
  Typography Dart generation
        │
Phase 2.7: Architecture Map
  DEX → All Composable screens → ViewModels → Navigation routes
  screens_architecture_spec.json + screens_summary.md
        │
★ Phase 2.8: Deep Screen Decompiler (NEW)
  Target Screen → Full bytecode walk (ALL instructions)
  → Component tree with child Composables (recursive)
  → Animation params (graphicsLayer: scale, rotation, alpha, blur)
  → ViewModel state mapping (StateFlow → UI binding)
  → Kotlin/Compose source synthesis
  Outputs: _decompiled.kt, _component_tree.json, _animations.json, _viewmodel.json
        │
★ Phase 2.9: Color Palette Pixel Sampling (NEW)
  Screenshot → Auto-region detection (or UI Automator bounds)
  → Pixel sampling at header/cards/grid/nav/buttons
  → K-means clustering → Brand palette (8-12 colors)
  → Cross-reference with ARSC tokens
  → Generate app_colors.dart
        │
Phase 3: Live Screen Inspection
  ADB Screencap (Pixel Truth)
  UI Automator XML Dump → Screen Spec JSON
  DP calculations from pixel bounds (px / density_scale)
        │
★ Phase 3.5: Live Interaction Capture (NEW)
  Swipe/Tap on real app → Document per component:
  - Carousel: blur sigma, rotation angle, scale factor, opacity
  - Toggles: transition animation type and duration
  - Navigation: tab indicator style, icon fill changes
  - Pull-to-refresh: indicator style and position
        │
Phase 4: Flutter Synthesis
  Clean Architecture (Features, Views, Widgets, BLoC)
  Design System Tokens (ARSC + pixel-sampled)
  Vector Icons with optical calibration (SizedBox containers)
  carousel_slider for pagers (never custom PageView)
  RTL Arabic at MaterialApp level + per-widget
        │
Phase 5: Verification
  flutter analyze → zero errors
  Emulator screencap → visual comparison
        │
★ Phase 5.5: Visual Diff QA Loop (NEW)
  Flutter screencap vs. Original app screencap
  → Side-by-side overlay comparison
  → Checklist: colors, dimensions, fonts, icons, spacing, RTL, animations
  → If mismatch: measure correct values → fix → re-capture
  → REPEAT until pixel-perfect
```

## Troubleshooting & Edge Cases

### 1. Production User Builds (`sdk_gphone64_x86_64-user`)
On production Android builds, `adb root` fails with:
`adbd cannot run as root in production builds`
- **Fix**: Never depend on `adb root`. Instead, patch the APK using `apk-mitm --debuggable`. This enables Frida or MITM proxies to attach without root permissions.

### 2. Payload-Level Encryption
If MITM proxy captures encrypted binary or Base64 payloads:
- **Formula**: Check APK native libraries (`libnative-lib.so`) or Java crypto calls via `frida_universal_bypass.js`.
- Common pattern: `Base64 Decode → AES-256-CBC Decrypt → Base64 Decode → GZIP Decompress → UTF-8 JSON`.

### 3. Font Not Rendering (CRITICAL — happened in Jaib)
If the extracted font shows as default sans-serif in Flutter:
1. Verify `pubspec.yaml` has the font family under `flutter: > fonts:`
2. Family name in Dart code MUST match `pubspec.yaml` exactly (case-sensitive)
3. Run `flutter pub get` → Hot-RESTART (not hot-reload)
4. If still broken: check that font files are not corrupt (open in system font viewer)

### 4. SVG Opacity Vanishing (CRITICAL — happened in Jaib)
When a decorative SVG overlay (card pattern, wave shape) becomes invisible:
1. Open the SVG — check for internal `opacity`, `fill-opacity`, or `style="opacity:0.2"`
2. If found: extract the raw white shapes as PNG (remove opacity from source)
3. In Flutter: wrap in `Opacity(opacity: 0.32, child: Image.asset('pattern.png'))`
4. Never nest `Opacity > SvgPicture` when the SVG already has internal opacity

### 5. Carousel Card Size Mismatch (happened in Jaib)
When carousel cards appear too large or too small:
1. Measure card bounds from UI Automator XML
2. Calculate dp: `dp = px / (device_density / 160)`
3. Set `viewportFraction = card_dp_width / screen_dp_width`
4. Calibrate `enlargeFactor` to match the scale difference seen in the live app
5. Apply blur/rotation/opacity to inactive cards (see Phase 3.5 interaction capture)

### 6. Icon Size Inconsistency (happened in Jaib)
When SVG icons in a grid appear at different sizes:
1. Check each SVG's `viewBox` attribute — different aspect ratios cause this
2. Wrap each icon in `SizedBox(height: fixed_dp)` as the outer container
3. Inside: set per-icon `width`/`height` to achieve optical uniformity
4. Example: 24x24 viewBox → `SizedBox(h:38, child: SVG(w:36, h:36))`
5. Example: 29x16 viewBox → `SizedBox(h:38, child: SVG(w:48, h:27))`

## Scripts Reference

| Script | Purpose | Phase |
|---|---|---|
| `app_patcher.py` | Pull + patch + reinstall APK | 1 |
| `asset_extractor.py` | Extract SVGs, PNGs, Lottie | 2 |
| `design_system_extractor.py` | Fonts + ARSC colors + typography | 2.5 |
| `screen_decompiler.py` | Architecture map of all screens | 2.7 |
| `deep_screen_decompiler.py` | **Full decompilation of any single screen** | 2.8 |
| `color_palette_extractor.py` | **Pixel-sample real colors from screenshot** | 2.9 |
| `ui_inspector.py` | Screenshot + UI hierarchy dump | 3 |
| `flutter_scaffolder.py` | Create Flutter project structure | 4 |
| `frida_universal_bypass.js` | SSL bypass + crypto interception | Support |
