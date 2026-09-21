---
name: app-replicator
description: "Universal mobile app cloner — reverse-engineer and replicate any Android mobile application into high-fidelity, pixel-perfect Flutter UI. Automated APK pulling, SSL pinning bypass/patching, asset extraction & vector-to-SVG conversion, live screen hierarchy inspection, deep screen decompilation with full component tree reconstruction, API payload decryption, and clean Flutter architecture synthesis."
argument-hint: "<package_name> [--device <serial>] [--flutter-dir <path>] [--screen <screen_name>]"
user-invocable: true
---

# App Replicator — Universal Android to Flutter Replicator (v2.0)

You are about to reverse-engineer and rebuild an Android application as a **pixel-perfect Flutter replica**.

This skill is the mobile counterpart to `site-replicator`. While `site-replicator` operates on web DOM and CSS, `app-replicator` operates directly on live Android device state, APK binary packages, DEX bytecode, vector drawables, and native network streams.

> **v2.0 UPGRADE**: Based on battle-tested real-world reverse-engineering of production apps (Jaib wallet, etc.), this version adds 17 Iron Rules, deep screen decompilation, live interaction capture, pixel-level color extraction, and visual diff QA.

---

## ⚡ Iron Rules — القواعد الحديدية (NEVER VIOLATE)

These rules were forged from real failures during production app replication. They are non-negotiable.

### Typography Rules

1. **FONT_ACTIVATION**: After extracting fonts, ALWAYS verify `pubspec.yaml` has the correct `fonts:` block with family name, asset path, and weight. Run `flutter pub get` and hot-restart (not hot-reload) to activate fonts. If the font doesn't render, check the family name in Dart matches the `pubspec.yaml` family name EXACTLY.
2. **FONT_FALLBACK**: Never use `google_fonts` package if the APK contains embedded custom fonts. Extract the real `.otf`/`.ttf` binaries and use `fontFamily:` directly.
3. **ARABIC_FONT_WEIGHTS**: Arabic fonts often bundle all weights in one `.otf`. If you see only one font file, register it under weight `400` and control visual weight with `FontWeight.w800` etc. in TextStyle.

### Color Rules

4. **DUAL_COLOR_EXTRACTION**: ARSC colors alone are NEVER enough. Always supplement with pixel sampling from live screenshots. Take the screenshot, sample specific coordinates (header bg, card bg, button bg, text colors) and cross-reference with ARSC values.
5. **RUNTIME_COLORS**: Many apps apply colors programmatically (dark mode overlays, card gradients). The ONLY source of truth is the live screenshot pixel — not the XML resource file.
6. **OPACITY_TRAP**: When an SVG/vector has internal `opacity` attributes AND you wrap it in a Flutter `Opacity` widget, the effect doubles and the graphic becomes invisible. Solution: Extract the raw shapes as a white-on-transparent PNG, then apply ONE external Opacity widget.

### Layout Rules

7. **DP_FROM_BOUNDS**: Calculate exact dp values from UI Automator bounds: `dp = px / (density / 160)`. For an emulator at 560dpi: `dp = px / 3.5`. Never eyeball padding values.
8. **CARD_SIZE_FROM_VIEWPORT**: For carousels, measure the card width from screenshot bounds, then calculate `viewportFraction = card_width_dp / screen_width_dp`.
9. **FIXED_ICON_CONTAINER**: SVG icons from different designers have wildly different viewBox aspect ratios. ALWAYS wrap each icon in a fixed-height `SizedBox` and calibrate `width`/`height` per-icon to achieve optical uniformity. A 29x16 viewBox icon needs different constraints than a 24x24 one.

### Carousel & Animation Rules

10. **USE_REAL_LIBRARIES**: Never build carousel/pager widgets from scratch. Use `carousel_slider` for Flutter. Match the original app's behavior exactly with `enlargeCenterPage`, `enlargeFactor`, `viewportFraction`, and `enlargeStrategy`.
11. **INSPECT_LIVE_GESTURES**: Before building any interactive component, swipe/tap/scroll on the real app and observe: Does the inactive card blur? Rotate? Scale? Fade? Document every visual effect seen during interaction.
12. **DECOMPILE_COMPOSE_EFFECTS**: In Jetpack Compose apps, the `graphicsLayer` block in `HorizontalPager` contains exact `scaleX`, `scaleY`, `rotationZ`, `alpha`, and blur values. Decompile these to match Flutter transforms exactly.

### RTL Rules

13. **FULL_APP_RTL**: For Arabic apps, wrap the ENTIRE `MaterialApp` in `Directionality(textDirection: TextDirection.rtl)` or set `locale` and `supportedLocales`. Every single screen, card, and list must flow right-to-left.
14. **PER_WIDGET_RTL**: Inside isolated widgets like wallet cards, add an explicit `Directionality(textDirection: TextDirection.rtl)` wrapper to guarantee RTL even when the widget is used in non-RTL test contexts.

### Asset Rules

15. **SVG_OPACITY_EXTRACTION**: If an SVG contains embedded `opacity` or `fill-opacity` attributes that make it semi-transparent, extract it as a white alpha-mask PNG instead. This prevents the "invisible overlay" bug where nested opacity makes the graphic vanish.
16. **PATTERN_OVERLAYS**: Decorative card patterns (arches, waves, geometric shapes) should be extracted as PNG with white fills on transparent background, then positioned with `Positioned(left:0, bottom:0)` inside a `Stack` with `Opacity` applied externally.

### Verification Rules

17. **SCREENSHOT_DIFF**: After every significant UI change, capture a new screenshot from the emulator and visually compare it side-by-side with the reference screenshot from the live app. This is the ONLY way to confirm pixel-perfect fidelity. Never trust code review alone.

### Bytecode & Conversion Rules (Strict Anti-Hallucination)

18. **BYTECODE_FIRST_RECONSTRUCTION (ZERO IMPROVISATION)**: If DEX bytecode or decompiled Composables are available, NEVER design UI from imagination, memory, or generic templates. Every single Flutter widget hierarchy MUST trace directly to decompiled Composable calls (`LazyColumn` → `ListView.builder`, `Box` → `Stack`/`Container`, `Row` → `Row`, `Text` → `Text`). Never add elements (e.g., Lottie animations, chevron icons, extra action buttons) that do not exist in the bytecode.
19. **ARSC_STRING_AUTHORITY**: UI labels, button texts, dialog titles, and hints must NEVER be guessed or translated from memory. Always resolve string resource IDs against decompiled `res/values/strings.xml` or `const-string` bytecode instructions (e.g., `R.string.proceed` → `استمرار`, `R.string.transaction_details` → `بيانات الحركة`).
20. **MULTI_COLOR_SVG_PRESERVATION**: Never apply a blanket monochrome `ColorFilter.mode(..., BlendMode.srcIn)` across an entire SVG asset unless it is proven to be strictly single-color monochrome. Vector assets containing semantic status dots, two-tone fills, or colored badge accents (e.g., `ic_calendar.svg`, `ic_export.svg`) must be rendered raw without destructive color filters.
21. **DIALOG_AND_SHEET_DECOMPILATION**: Dialogs, bottom sheets, date pickers, and alerts are first-class screens. Locate their Composable method or DialogFragment in DEX/smali (e.g., `Lra/w;::o`, `Lra/m;::e`), decompile their component tree, and reconstruct them with the exact same 100% rigor as main screens.
22. **DECRYPTED_PAYLOAD_SCHEMA_CONFORMANCE**: When decrypted network traffic (e.g., intercepted mitmproxy logs or decrypted API JSON files) is available, Flutter data models and mock instances must match the exact schema and real values from intercepted responses (e.g., `decrypted_ExecuteE2_response.json`), matching field names, date formats, and status codes.

---

## Core Pipeline

```
┌────────────────────────────────────────────────────────┐
│ Phase 0: Discovery & Setup                             │
│ ADB devices → Package verification → Environment check │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 1: Reconnaissance & Patching                     │
│ Pull Split APKs → Patch SSL & Debuggable → Reinstall   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 2: Universal Asset Extraction                    │
│ Vector XMLs → Standard SVGs | High-DPI PNGs | Lottie   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 2.5: Design System & Custom Font Extraction      │
│ Fonts → ARSC Tokens → pubspec.yaml → Dart Themes       │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 2.7: Screen Decompilation & Architectural Map    │
│ DEX → Composables → ViewModels → Navigation → States   │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ ★ Phase 2.8: Deep Screen Decompiler (NEW)              │
│ Target Screen → Full Component Tree → Kotlin Synthesis │
│ → Layout params → Animation configs → Data models      │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 2.9: Color Palette Pixel Sampling (NEW)          │
│ Screenshot → Region Sampling → Brand Palette → Dart    │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 3: Live Screen Inspection                        │
│ Screenshot (Visual Truth) + UI Automator XML Dump      │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ ★ Phase 3.5: Live Interaction Capture (NEW)            │
│ Swipe/Tap gestures → Observe blur/rotation/scale/fade  │
│ → Document all transition effects per component        │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 4: Flutter Architecture Synthesis                │
│ Clean Architecture + BLoC + Design Tokens + RTL Arabic │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Phase 5: Verification & Quality Assurance              │
│ flutter analyze + Screenshot Diff + Emulator Screencap │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ ★ Phase 5.5: Visual Diff QA Loop (NEW)                 │
│ Side-by-side overlay comparison of Flutter vs. Original │
│ Iterate until pixel-level match confirmed              │
└────────────────────────────────────────────────────────┘
```

---

## Phase 0: Discovery & Setup

### 0.1 Parse Arguments

Target package: `$ARGUMENTS` (e.g., `com.ahd.jaib`, `com.example.app`).
Default device serial: `emulator-5554` (or target device from `adb devices`).

### 0.2 Device Verification

Check connected ADB devices:

```bash
adb devices
```

Ensure the target app is installed:

```bash
adb -s <serial> shell pm list packages | grep <package_name>
```

---

## Phase 1: Pull & Patch App

To intercept network traffic on Android 7+ and inspect memory without root permissions:

Run the automated patcher script:

```bash
python <skill-dir>/scripts/app_patcher.py <package_name> <device_serial>
```

### What this does:

1. Resolves all split APKs via `pm path <package_name>`
2. Pulls all parts (`base.apk`, `split_config.*.apk`) to local folder
3. Bundles them into an `.apks` zip
4. Patches network security config with `apk-mitm` adding `--debuggable`
5. Uninstalls the original app and reinstalls the patched APKs via `adb install-multiple`

> **Note for Production User Builds:** If `adb root` fails with `adbd cannot run as root in production builds`, the `--debuggable` flag injected by `app_patcher.py` allows Frida and debugging tools to attach directly without root.

---

## Phase 2: Asset Extraction & Vector Conversion

Android apps use Vector Drawables (`<vector>`) and multi-DPI directories (`drawable-xxxhdpi`, `mipmap-xxhdpi`).

Run the universal asset extractor:

```bash
python <skill-dir>/scripts/asset_extractor.py <path_to_apk_or_res> --output extracted_assets/<app_slug>
```

### Conversion Capabilities:

- **Vector Drawables to SVGs**: Parses Android XML vector paths, groups, transforms, clip-paths, and colors into standard W3C SVGs.
- **DPI Ranking**: Automatically selects the highest resolution raster image (`xxxhdpi` > `xxhdpi` > `xhdpi`).
- **Boilerplate Noise Filtering**: Strips out Android support libraries (`abc_`, `androidx_`, `notification_`, `mtrl_`).
- **Media & Lottie**: Gathers all `.json` Lottie files and raw audio (`.mp3`, `.wav`, `.ogg`).

### Post-Extraction Checks (Iron Rule #15, #16):

- Scan all SVGs for embedded `opacity` or `fill-opacity` attributes.
- For decorative overlays (card patterns, wave shapes), convert to white-on-transparent PNG.
- Log warnings for any SVG with `opacity < 0.5` — these will likely vanish in Flutter `Opacity` nesting.

---

## Phase 2.5: Design System & Custom Font Extraction

Extract exact brand typography and compiled ARSC design tokens directly from the APK package:

```bash
python <skill-dir>/scripts/design_system_extractor.py <path_to_apk_or_apks> --flutter-dir <flutter_project_path>
```

### What this extracts:

1. **True Font Binaries (`.otf`, `.ttf`)**: Pulls all embedded custom font families from `res/font/` or `assets/fonts/` into Flutter's `assets/fonts/`.
2. **Font Weights & Declarations**: Automatically detects font weights and injects the `fonts:` manifest into `pubspec.yaml`.
3. **ARSC Design Tokens**: Decodes Android compiled binary resource tables (`resources.arsc`) to recover exact brand color values.
4. **Dart Design System**: Generates `app_typography.dart` and `app_theme.dart`.

### Post-Extraction Verification (Iron Rule #1, #2):

```bash
# ALWAYS verify font activation after extraction:
cd <flutter_project>
flutter pub get
# Then hot-RESTART (not hot-reload) to activate new fonts
```

---

## Phase 2.7: Screen Decompilation & Architectural UI Mapping

Decompile all screens, ViewModels, navigation route graphs, and API contracts from APK DEX bytecode:

```bash
python <skill-dir>/scripts/screen_decompiler.py <path_to_apk_or_apks> --output <output_dir>
```

### What this maps & extracts:

1. **Navigation Graph & Routes**: Discovers all screen paths (`/home`, `/cards`, `/transfer`, `/reports`, `/profile`, `/settings`, etc.).
2. **Jetpack Compose Screens & UI Trees**: Identifies all Composable screen functions, layout scaffolds, and parameter signatures.
3. **ViewModels & Reactive State Flows**: Maps `StateFlow` and `MutableState` properties.
4. **Exported Architectural Artifacts**:
    - `screens_architecture_spec.json`: Machine-readable mapping of all screens.
    - `screens_summary.md`: Human-readable inventory.

---

## ★ Phase 2.8: Deep Screen Decompiler (NEW)

This is the **killer feature**. Given a target screen name, this phase fully decompiles that screen into a readable Kotlin/Compose source reconstruction with all its components, data models, animations, and state management.

### Usage:

```bash
python <skill-dir>/scripts/deep_screen_decompiler.py <apk_path> --screen "Home" --output <output_dir>
```

### What it does (step by step):

1. **Screen Discovery**: Finds the target Composable class by matching route name (e.g., "Home" → `Lib/y;::c`) from the `screens_architecture_spec.json`.
2. **Full Method Bytecode Walk**: For every method in the target class, walks ALL bytecode instructions — not just `const-string` and `invoke` — capturing:
    - `const-string`: All UI labels, resource keys, error messages
    - `invoke-*`: All function calls, Compose widget invocations, ViewModel state reads
    - `sget/sput`: Static field accesses (shared prefs, singletons)
    - `iget/iput`: Instance field accesses (model properties, view state)
    - `new-instance`: All data classes and models instantiated
3. **Component Tree Reconstruction**: From the invoke graph, builds a tree of Composable calls:
    ```
    HomeScreen (Lib/y;::c)
    ├── HomeAppBar (Lib/h;)
    ├── WalletCardCarousel (Lib/o;)
    │   ├── HorizontalPager + graphicsLayer (scale, rotation, alpha)
    │   └── WalletCard (Lbb/i;::c)
    │       ├── card, onShowBalance, onCheckedChange
    │       └── Image(account_card_pattern.svg)
    ├── OnlineAdsBanner (Lib/p;)
    ├── HomeServicesGrid (Leb/d;)
    └── RecentTransactionItem (Lib/x;)
    ```
4. **Animation & Effect Extraction**: Detects `graphicsLayer`, `Modifier.blur`, `animateFloatAsState`, `AnimatedVisibility`, and extracts:
    - `scaleX`, `scaleY` values
    - `rotationZ` angles (converted to radians for Flutter `Transform.rotate`)
    - `alpha` transparency values
    - Blur sigma values
5. **ViewModel State Mapping**: For the associated ViewModel class (e.g., `Lib/i0;`):
    - Lists all `StateFlow` / `MutableStateFlow` fields with their types
    - Maps state → UI binding (which Composable reads which state)
6. **Output Artifacts**:
    - `<screen>_decompiled.kt`: Human-readable Kotlin/Compose source reconstruction
    - `<screen>_component_tree.json`: Machine-readable component hierarchy
    - `<screen>_animations.json`: All detected animation configs
    - `<screen>_viewmodel.json`: ViewModel state map

### Deep Decompiler Strategy:

```
For each target Composable method:
  1. Walk bytecode → extract ALL const-string values (= UI text, keys)
  2. Walk bytecode → extract ALL invoke-virtual/static targets (= widget tree)
  3. For each invoked class:
     a. If it's a Composable (has Composer param): RECURSE into it
     b. If it's a ViewModel: map its StateFlow fields
     c. If it's a data class: extract its constructor params (= model fields)
  4. For graphicsLayer blocks: extract float constants (= animation params)
  5. Reconstruct readable Kotlin with actual parameter names from spec
```

### Jetpack Compose to Flutter Translation Matrix:

| Jetpack Compose Element                   | Bytecode Signature                                | Flutter Equivalent                                  |
| ----------------------------------------- | ------------------------------------------------- | --------------------------------------------------- |
| `LazyColumn { items(...) }`               | `LazyDslKt.items(...)`                            | `ListView.builder(...)`                             |
| `Box(contentAlignment = ...)`             | `BoxKt.Box(...)`                                  | `Stack(alignment: ...)` or `Container(...)`         |
| `Row(horizontalArrangement = ...)`        | `RowKt.Row(...)`                                  | `Row(mainAxisAlignment: ...)`                       |
| `Column(verticalArrangement = ...)`       | `ColumnKt.Column(...)`                            | `Column(mainAxisAlignment: ...)`                    |
| `Surface(shape = ..., color = ...)`       | `SurfaceKt.Surface(...)`                          | `Material(...)` / `Container(decoration: ...)`      |
| `Modifier.padding(all = X.dp)`            | `PaddingKt.padding(...)`                          | `Padding(padding: EdgeInsets.all(X))`               |
| `Modifier.clip(RoundedCornerShape(X.dp))` | `ClipKt.clip(...)`                                | `ClipRRect(borderRadius: BorderRadius.circular(X))` |
| `Modifier.border(width, color, shape)`    | `BorderKt.border(...)`                            | `BoxDecoration(border: Border.all(...))`            |
| `Modifier.clickable { ... }`              | `ClickableKt.clickable(...)`                      | `InkWell(...)` or `GestureDetector(...)`            |
| `Text(text = stringResource(id), ...)`    | `StringResources_androidKt.stringResource(...)`   | Extract string value from ARSC → `Text(...)`        |
| `Icon(painter = painterResource(id))`     | `PainterResources_androidKt.painterResource(...)` | `SvgPicture.asset(...)`                             |

---

## Phase 2.9: Color Palette Pixel Sampling (NEW)

ARSC colors represent design-time tokens. Runtime colors (dark mode overlays, gradients, card tints) can only be captured from the live pixel buffer.

### Usage:

```bash
python <skill-dir>/scripts/color_palette_extractor.py --serial <device_serial> --output <flutter_project>/lib/core/theme/
```

### Sampling Strategy:

1. **Capture** high-res screenshot from connected device.
2. **Define sampling regions** (auto-detected from UI Automator bounds):
    - Header/AppBar background: top 200px center
    - Primary card background: center of first card bounds
    - Secondary card background: center of second card bounds
    - Screen background: edges and bottom areas
    - Button/FAB fill: center of clickable elements
    - Text colors: sample text-bearing regions
3. **Cluster colors** using K-means to identify the brand palette (typically 8-12 distinct colors).
4. **Cross-reference** with ARSC tokens: match sampled hex values to named tokens where possible.
5. **Generate** `app_colors.dart` with named constants and hex values verified against live pixels.

---

## Phase 3: Live Screen Inspection (Visual Truth)

Screenshots and UI Automator dumps provide the exact ground truth:

```bash
python <skill-dir>/scripts/ui_inspector.py --serial <device_serial> --output-dir inspected_screen --screen-name home_screen
```

### Outputs Generated:

1. `home_screen.png`: High-resolution pixel truth.
2. `home_screen.xml`: Full node hierarchy with exact coordinates `[left,top][right,bottom]`.
3. `home_screen_spec.json`: Formatted component tree, text labels, resource IDs, clickable states, and dimensions.

### Post-Inspection Calculations (Iron Rule #7, #8):

```python
# Convert pixel bounds to dp:
density_dpi = 560  # from adb shell wm density
scale = density_dpi / 160  # = 3.5 for 560dpi
dp_width = pixel_width / scale
dp_height = pixel_height / scale
dp_padding = pixel_padding / scale
```

---

## ★ Phase 3.5: Live Interaction Capture (NEW)

Before building any interactive component, you MUST observe the real app's behavior during user interaction.

### Checklist for Every Interactive Component:

| Component             | What to Observe                                                       | How to Capture                                  |
| --------------------- | --------------------------------------------------------------------- | ----------------------------------------------- |
| **Carousel/Pager**    | Swipe → Check: side card blur? rotation angle? scale factor? opacity? | Screenshot at rest + mid-swipe + edge positions |
| **Balance Toggle**    | Tap eye icon → Check: dots↔amount transition animation                | Screenshot before + after tap                   |
| **Pull-to-Refresh**   | Pull down → Check: indicator style, color, position                   | Screenshot during pull                          |
| **Bottom Nav**        | Tap each tab → Check: icon fill change, label bold, indicator dot     | Screenshot each tab state                       |
| **Card Tap**          | Tap wallet card → Check: navigation destination, ripple effect        | Observe + screenshot                            |
| **Service Grid Item** | Tap service → Check: ripple, navigation, haptic feedback              | Observe behavior                                |

### Documentation Format:

For each interactive element, document:

```yaml
component: WalletCardCarousel
interaction: horizontal_swipe
effects:
  active_card:
    background: primary_red (#E60000)
    scale: 1.0
    rotation: 0
    blur: 0
    opacity: 1.0
  inactive_card:
    background: dark_surface (#1E1E1E)
    scale: 0.84 (enlargeFactor: 0.16)
    rotation: ±0.085 radians (inward lean)
    blur: sigma 2.5
    opacity: 0.85
  indicator:
    active: primary_red circle (7dp)
    inactive: white circle (7dp)
    count: matches card count
```

---

## Phase 4: Flutter Synthesis

### 4.1 Project Scaffolding

Create the Clean Architecture Flutter project:

```bash
python <skill-dir>/scripts/flutter_scaffolder.py <project_name> --assets extracted_assets/<app_slug>
```

### 4.2 Architecture Standards:

- **Directory Structure**:
    - `lib/core/theme/` (colors, typography, theme tokens)
    - `lib/features/<feature>/presentation/views/` (screen compositions)
    - `lib/features/<feature>/presentation/widgets/` (isolated, modular UI components)
    - `lib/features/<feature>/presentation/bloc/` (state management)
    - `lib/features/<feature>/data/models/` (typed data classes)
- **Asset Declaration**: Uses extracted SVGs via `flutter_svg` and images from `assets/images/`.
- **RTL & Localization**: Use the EXTRACTED custom font (Iron Rule #2), full Arabic RTL alignment (Iron Rule #13, #14).

### 4.3 Flutter Build Rules (from Iron Rules):

- **Carousel**: Use `carousel_slider` package. Set `enlargeCenterPage: true`, calibrate `viewportFraction` from screenshot measurements (Rule #10).
- **Icons**: Wrap every SVG icon in `SizedBox(height: <fixed>)` with per-icon width/height calibration (Rule #9).
- **Cards**: Use `ClipRRect` + `Stack` for pattern overlays. Apply `ImageFilter.blur` and `Transform.rotate` on inactive cards (Rule #12).
- **Colors**: Use pixel-sampled values, not ARSC-only (Rule #4, #5).
- **Fonts**: Extract real binary fonts, register in pubspec, hot-restart to verify (Rule #1, #2).

---

## Phase 5: Verification & Quality Assurance

1. **Static Analysis**:
    ```bash
    flutter analyze
    ```
    Must pass with zero errors.
2. **Visual Fidelity** (Iron Rule #17):
    ```bash
    # Capture from emulator
    adb -s <serial> shell screencap -p /sdcard/flutter_result.png
    adb -s <serial> pull /sdcard/flutter_result.png
    ```
    Compare the Flutter rendered layout against the captured reference screenshot from the live app.

---

## ★ Phase 5.5: Visual Diff QA Loop (NEW)

This is an iterative loop that runs until the Flutter output matches the original app pixel-perfectly:

```
REPEAT:
  1. Capture Flutter emulator screenshot
  2. Capture original app screenshot (same screen, same state)
  3. Overlay and compare:
     - Background colors match?
     - Card dimensions match?
     - Font rendering matches?
     - Icon sizes uniform?
     - Spacing and padding correct?
     - RTL alignment correct?
     - Animation effects match (blur, rotation, scale)?
  4. If differences found:
     a. Identify the exact component with the mismatch
     b. Measure the correct values from the original screenshot
     c. Update the Flutter widget with corrected values
     d. Hot-reload and re-capture
  5. UNTIL: No visible differences remain
```

---

## Autonomous Invariants

- NEVER build UI from imagination, visual guessing, or generic Flutter templates when DEX bytecode or Composable methods are available.
- NEVER invent fictional elements (e.g., Lottie animations, extra chevrons, fabricated buttons) not present in the decompiled bytecode.
- NEVER use placeholder gray boxes when real vector icons exist in `extracted_assets/`.
- NEVER apply blanket monochrome `ColorFilter` on multi-color SVG assets containing accent colors.
- NEVER guess Arabic strings or button titles — always look up the exact string in decompiled ARSC `strings.xml`.
- ALWAYS treat dialogs, bottom sheets, and alert modals as first-class screens requiring full decompilation before implementation.
- NEVER ask the user how to fix layout padding or which colors to use; determine them directly from the screenshot, XML dump, and bytecode parameters.
- NEVER build custom carousel/pager widgets when `carousel_slider` exists.
- NEVER trust ARSC colors alone — always pixel-sample the live screenshot.
- NEVER skip font verification after extraction — always hot-restart and confirm rendering.
- NEVER use `google_fonts` when the APK contains embedded custom font binaries.
- ALWAYS apply full RTL for Arabic apps at the MaterialApp level AND per-widget level.
- ALWAYS wrap SVG icons in fixed-height containers with per-icon optical calibration.
- ALWAYS capture a verification screenshot after every significant UI change.
- Deliver production-ready, clean, maintainable Flutter code that is indistinguishable from the original app.
