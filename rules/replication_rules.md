# App Replicator — Replication Rules (القواعد التفصيلية)

> These rules were extracted from battle-testing the app-replicator against production apps.
> Every rule maps to a real failure that caused wasted time during replication.

---

## 1. Typography Rules

### Rule T1: Font Binary Extraction & Activation
```
EXTRACT → REGISTER → RESTART → VERIFY
```
1. Extract `.otf`/`.ttf` from APK's `res/font/` and `assets/fonts/`
2. Copy to Flutter `assets/fonts/`
3. Add to `pubspec.yaml` under `flutter: > fonts:`
4. Run `flutter pub get`
5. **Hot-RESTART** (not hot-reload) — fonts only activate on restart
6. Verify in emulator — if text renders as default, the family name is wrong

### Rule T2: Never Use Google Fonts for Embedded Fonts
If the APK ships with custom font files, those ARE the brand fonts.
Using `google_fonts` introduces network dependency and wrong font weights.

### Rule T3: Arabic Font Weight Detection
Arabic fonts often ship as a single file. Weight detection:
```
file contains "thin"         → weight: 100
file contains "light"        → weight: 300  
file contains "regular"      → weight: 400
file contains "semibold"     → weight: 600
file contains "bold"         → weight: 700
file contains "extrabold"    → weight: 800
single file, no weight hint  → weight: 400 (control with FontWeight in code)
```

---

## 2. Color Rules

### Rule C1: Dual-Source Color Extraction
```
ARSC Colors (design-time) + Pixel Sampling (runtime) = True Palette
```
ARSC gives you named tokens (`color_primary`, `color_surface`).
Pixel sampling gives you what actually renders (dark mode, gradients, overlays).

### Rule C2: Pixel Sampling Coordinates
Sample these regions from the live screenshot:
| Region | Pixel Location | What It Captures |
|---|---|---|
| Header BG | (screen_width/2, 150) | App bar background |
| Screen BG | (50, screen_height - 200) | Main background |
| Primary Card | center of card bounds from UI Automator | Active card color |
| Secondary Card | center of inactive card bounds | Inactive card color |
| Primary Button | center of FAB/CTA bounds | Primary action color |
| Text Primary | text-bearing region | Primary text color |
| Text Secondary | subtitle region | Secondary text color |

### Rule C3: Opacity Double-Application Trap
```
SVG with opacity="0.2" → Opacity(opacity: 0.2, child: SvgPicture...)
Actual result: 0.2 × 0.2 = 0.04 = INVISIBLE
```
**Fix**: Extract SVG shapes as white-on-transparent PNG (opacity=1.0), then apply ONE Opacity widget.

---

## 3. Layout Rules

### Rule L1: DP Calculation from Pixel Bounds
```dart
// From UI Automator: bounds="[100,200][700,600]"
// Emulator density: 560dpi (wm density)
final scale = 560 / 160; // = 3.5
final widthDp = (700 - 100) / scale; // = 171.4 dp
final heightDp = (600 - 200) / scale; // = 114.3 dp
final paddingLeftDp = 100 / scale; // = 28.6 dp
```

### Rule L2: Carousel Viewport Fraction
```dart
// Measure from screenshot:
// Card visible width: ~820px on 1440px-wide screen
// viewportFraction = 820 / 1440 = 0.57 (this is the visible portion)
// But carousel_slider viewportFraction works differently:
// It's the fraction of the viewport each item occupies
// Calibrate empirically: start at 0.72-0.78 and adjust
```

### Rule L3: Fixed Icon Container Pattern
```dart
// BAD: Icons with different viewBox sizes appear misaligned
SvgPicture.asset('ic_transfer.svg', width: 36, height: 36); // 24x24 viewBox → OK
SvgPicture.asset('ic_entertainment.svg', width: 36, height: 36); // 29x16 viewBox → SQUISHED

// GOOD: Fixed container with per-icon optical calibration
SizedBox(
  height: 38, // Fixed outer height for all icons
  child: SvgPicture.asset(
    'ic_entertainment.svg',
    width: 48,    // Wider to compensate short viewBox
    height: 27,   // Shorter to maintain aspect ratio
    fit: BoxFit.contain,
  ),
)
```

---

## 4. Carousel & Animation Rules

### Rule A1: Library Selection
| Pattern | Flutter Library | Key Config |
|---|---|---|
| Horizontal card pager with scale | `carousel_slider` | `enlargeCenterPage: true, enlargeFactor: 0.16` |
| Vertical scroll pager | `PageView` | `scrollDirection: Axis.vertical` |
| Image slider with autoplay | `carousel_slider` | `autoPlay: true` |
| Tinder-style card stack | `flutter_card_swiper` | — |

### Rule A2: Inactive Card Effects (from Jetpack Compose graphicsLayer)
```dart
// Jetpack Compose original:
// graphicsLayer {
//   scaleX = 0.84f; scaleY = 0.84f;
//   rotationZ = if (offset < 0) 2.8f else -2.8f;
//   alpha = 0.82f;
// }

// Flutter equivalent:
if (!isCurrent) {
  final rotationAngle = index < currentPage ? 0.085 : -0.085; // radians
  return Transform.rotate(
    angle: rotationAngle,
    child: ImageFiltered(
      imageFilter: ImageFilter.blur(sigmaX: 2.5, sigmaY: 2.5),
      child: Opacity(opacity: 0.85, child: cardWidget),
    ),
  );
}
```

### Rule A3: Dot Indicator Matching
```dart
// Match the original indicator exactly:
// - Shape: circle (not pill)
// - Active color: primary red
// - Inactive color: white with alpha
// - Size: 7dp diameter
// - Animation: none (simple swap)
Container(
  width: 7, height: 7,
  decoration: BoxDecoration(
    color: isActive ? AppColors.primary : Colors.white.withOpacity(0.8),
    shape: BoxShape.circle,
  ),
)
```

---

## 5. RTL Rules

### Rule R1: App-Level RTL
```dart
MaterialApp(
  locale: const Locale('ar'),
  supportedLocales: const [Locale('ar')],
  localizationsDelegates: [
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ],
  builder: (context, child) => Directionality(
    textDirection: TextDirection.rtl,
    child: child!,
  ),
)
```

### Rule R2: Per-Widget RTL Safety
Even with app-level RTL, isolated widgets should declare their own:
```dart
Directionality(
  textDirection: TextDirection.rtl,
  child: Padding(
    padding: const EdgeInsets.symmetric(horizontal: 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start, // Start = Right in RTL
      children: [...],
    ),
  ),
)
```

---

## 6. Deep Screen Decompilation Rules

### Rule D1: Target Screen Resolution
To decompile a specific screen, resolve its Composable class from `screens_architecture_spec.json`:
```
Screen Route → screens_summary.md → Component Table → Class Name → DEX bytecode
Example: "Home" → Lib/y;::c (main screen composable)
```

### Rule D2: Full Bytecode Walking (not just strings)
The basic decompiler only extracts `const-string` and `invoke-*`. The deep decompiler must walk ALL instructions:
```
const-string    → UI labels, error messages, API keys
invoke-virtual  → method calls (state reads, navigation)
invoke-static   → utility calls, factory methods
invoke-direct   → constructor calls (data class instantiation)
new-instance    → object creation (what models are used)
sget/sput       → static field access (shared state, singletons)
iget/iput       → instance field access (ViewModel properties)
const/4, const  → numeric constants (dp values, durations, angles)
```

### Rule D3: Recursive Component Tree
When a Composable invokes another Composable:
1. Record the call as a child in the component tree
2. Recursively walk the child's bytecode
3. Extract its parameters (= the widget's API surface)
4. Map data flow: which ViewModel state feeds which widget param

### Rule D4: Animation Parameter Extraction
Look for these patterns in bytecode:
```
const v0, 0x3F570A3D   → float 0.84 (scale factor)
const v0, 0x40333333   → float 2.8 (rotation degrees)
const v0, 0x3F51EB85   → float 0.82 (alpha)
```
Convert Compose degrees to Flutter radians: `radians = degrees * π / 180`

### Rule D5: Kotlin Synthesis Output
The decompiled output should be readable Kotlin/Compose, not raw bytecode:
```kotlin
@Composable
fun HomeScreen(
    navController: NavHostController,
    viewModel: HomeViewModel,  // Lib/i0
) {
    val accounts by viewModel.accountsState.collectAsState()
    val isBalanceVisible by viewModel.isBalanceVisibleState.collectAsState()
    
    LazyColumn {
        item { HomeAppBar(greeting = "جمعتك مباركة", userName = viewModel.currentUserName) }
        item { WalletCardCarousel(accounts = accounts, isBalanceVisible = isBalanceVisible) }
        item { OnlineAdsBanner(ads = onlineAds) }
        item { HomeServicesGrid(services = homeServiceList) }
        items(recentTransactions) { RecentTransactionItem(transaction = it) }
    }
}
```

---

## 7. Verification Rules

### Rule V1: Screenshot After Every Change
```bash
# After EVERY significant UI change:
adb -s emulator-5554 shell screencap -p /sdcard/verify.png
adb -s emulator-5554 pull /sdcard/verify.png
```
Compare visually. If something looks wrong, fix it before moving on.

### Rule V2: Side-by-Side Comparison Checklist
- [ ] Background color matches
- [ ] Card dimensions match
- [ ] Card spacing matches
- [ ] Font family renders correctly (not default sans-serif)
- [ ] Font sizes match
- [ ] Icon sizes are uniform
- [ ] RTL alignment is correct
- [ ] Carousel behavior matches (blur, rotation, scale)
- [ ] Indicator dots match (shape, color, size)
- [ ] Bottom nav matches (icons, labels, active state)

### Rule V3: Hot-Reload vs Hot-Restart
| Change Type | Required Action |
|---|---|
| Widget tree changes | Hot-reload (`r`) |
| New font registration | Hot-restart (`R`) |
| New asset files | Hot-restart (`R`) |
| pubspec.yaml changes | `flutter pub get` → Hot-restart (`R`) |
| New package dependency | `flutter pub get` → Hot-restart (`R`) |

---

## 8. Bytecode-to-Flutter Translation & Decompilation Integrity (القواعد الصارمة لفك وتحويل الكود)

### Rule B1: Zero Hallucination UI Protocol (ممنوع البناء من الرأس)
When DEX bytecode or decompiled Composables exist, NEVER invent, guess, or create UI structures based on general assumptions:
1. Locate the exact Composable method or class in DEX/JADX/smali.
2. Read the full instruction sequence and child invocations.
3. Every Flutter widget (`Row`, `Column`, `ListView`, `Padding`, `Container`) must map 1-to-1 to a corresponding Composable call in the bytecode.
4. If an element does NOT exist in the decompiled method (such as a Lottie animation, decorative chevron, or custom close button), DO NOT add it.

### Rule B2: Methodical Composable Bytecode Walk
Before writing any screen, dialog, or card widget:
1. **Walk Child Invocations**: Identify all helper composables (e.g. `Lla/h1;::x` for transaction items).
2. **Inspect Modifiers**: Extract exact padding values, corner radii (`RoundedCornerShape`), and border parameters.
3. **Map State & Fields**: Check which fields are passed to the composable (e.g., `description`, `balanceAfter`, `receiverName`).
4. **Translate to Flutter**: Use the Composable-to-Flutter translation matrix directly.

### Rule B3: Resource ID to String Resolution via ARSC (المرجعية الصارمة للنصوص)
NEVER guess Arabic text or action button titles from memory:
- Look up the hex resource ID (e.g., `0x7f130...`) in `resources.arsc` or decompiled `strings.xml`.
- If the bytecode references `R.string.proceed`, the text is "استمرار" (NOT "متابعة").
- If the dialog title is `R.string.transaction_details`, the text is "بيانات الحركة" (NOT "إيصال العملية").
- Always use the literal, exact string extracted from the application's resources.

### Rule B4: Safe SVG Rendering Protocol (حماية الأيقونات متعددة الألوان)
- **Monochrome Icons**: Only apply `ColorFilter.mode(..., BlendMode.srcIn)` if the vector has a single uniform color and is intended to be tinted dynamically (e.g., unselected nav tab icons).
- **Multi-color / Accented Icons**: Never tint icons with semantic accents (e.g., `ic_calendar.svg` with red calendar dots, `ic_export.svg` with red arrows). Render them directly with `SvgPicture.asset(path)` so internal colored layers remain intact.

### Rule B5: Intercepted Network Payload Fidelity (التطابق التام مع بيانات الشبكة المفكوكة)
- When decrypted network payloads exist (e.g., `decrypted_ExecuteE2_response.json` from mitmproxy/Frida):
  - Model class fields must match the actual JSON keys (`TransactionDate`, `Amount`, `BalanceAfter`, etc.).
  - Mock datasets used for UI testing must use real records from the intercepted responses, not generic placeholder values.
