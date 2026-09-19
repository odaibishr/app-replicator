#!/usr/bin/env python3
"""
App Replicator - Flutter Project Scaffolder & Architecture Generator
====================================================================
Bootstraps a production-ready Flutter replica project:
1. Runs 'flutter create' with clean package identity
2. Adds standard UI & state management packages (flutter_svg, google_fonts, lottie, flutter_bloc, etc.)
3. Imports extracted APK assets (SVGs, PNGs, animations, sounds)
4. Updates pubspec.yaml with complete asset declarations
5. Generates Clean Architecture directory structure and Design System tokens (colors, typography, theme)
6. Supports RTL Arabic & LTR English localization out of the box
"""

import os
import sys
import shutil
import argparse
import subprocess
from pathlib import Path

ESSENTIAL_PACKAGES = [
    "flutter_svg",
    "google_fonts",
    "flutter_bloc",
    "equatable",
    "intl",
    "lottie",
    "cached_network_image",
    "smooth_page_indicator"
]

COLORS_DART_TEMPLATE = """import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // Primary & Brand
  static const Color primary = Color(0xFFE50914);
  static const Color primaryDark = Color(0xFFB80710);
  static const Color primaryLight = Color(0xFFFF4D4D);
  static const Color accent = Color(0xFFFFC107);

  // Backgrounds (Dark Mode First)
  static const Color background = Color(0xFF0D1117);
  static const Color surface = Color(0xFF161B22);
  static const Color card = Color(0xFF21262D);
  static const Color border = Color(0xFF30363D);

  // Text colors
  static const Color textPrimary = Color(0xFFF0F6FC);
  static const Color textSecondary = Color(0xFF8B949E);
  static const Color textMuted = Color(0xFF6E7681);

  // Status & Actions
  static const Color success = Color(0xFF2EA043);
  static const Color warning = Color(0xFFD29922);
  static const Color danger = Color(0xFFF85149);
  static const Color info = Color(0xFF58A6FF);
}
"""

THEME_DART_TEMPLATE = """import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'app_colors.dart';

class AppTheme {
  AppTheme._();

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AppColors.background,
      primaryColor: AppColors.primary,
      cardColor: AppColors.card,
      dividerColor: AppColors.border,
      textTheme: GoogleFonts.cairoTextTheme(ThemeData.dark().textTheme).copyWith(
        displayLarge: GoogleFonts.cairo(color: AppColors.textPrimary, fontWeight: FontWeight.bold),
        titleLarge: GoogleFonts.cairo(color: AppColors.textPrimary, fontWeight: FontWeight.w700),
        bodyLarge: GoogleFonts.cairo(color: AppColors.textPrimary),
        bodyMedium: GoogleFonts.cairo(color: AppColors.textSecondary),
        labelLarge: GoogleFonts.cairo(color: AppColors.textPrimary, fontWeight: FontWeight.w600),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.background,
        elevation: 0,
        centerTitle: true,
      ),
    );
  }
}
"""

MAIN_DART_TEMPLATE = """import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'core/theme/app_theme.dart';
import 'features/home/presentation/views/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ReplicaApp());
}

class ReplicaApp extends StatelessWidget {
  const ReplicaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'App Replica',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.darkTheme,
      locale: const Locale('ar'), // Default to Arabic RTL
      supportedLocales: const [
        Locale('ar'),
        Locale('en'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const HomeScreen(),
    );
  }
}
"""

HOME_SCREEN_TEMPLATE = """import 'package:flutter/material.dart';
import '../../../../core/theme/app_colors.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      body: const SafeArea(
        child: Center(
          child: Text(
            'Replicated Screen',
            style: TextStyle(color: AppColors.textPrimary, fontSize: 20),
          ),
        ),
      ),
    );
  }
}
"""

def scaffold_flutter_app(project_name: str, target_dir: Path, assets_src_dir: Path = None):
    project_path = target_dir / project_name
    print(f"[*] Scaffolding Flutter project: {project_path}...")

    if not project_path.exists():
        subprocess.run(["flutter", "create", "--org", "com.replica", "--project-name", project_name, str(project_path)], check=True)
    else:
        print(f"[!] Target folder {project_path} already exists. Skipping 'flutter create'...")

    print("[*] Adding core dependencies...")
    subprocess.run(["flutter", "pub", "add"] + ESSENTIAL_PACKAGES, cwd=str(project_path), check=True)

    # Clean architecture directories
    dirs_to_make = [
        project_path / "lib" / "core" / "constants",
        project_path / "lib" / "core" / "theme",
        project_path / "lib" / "core" / "utils",
        project_path / "lib" / "features" / "home" / "presentation" / "views",
        project_path / "lib" / "features" / "home" / "presentation" / "widgets",
        project_path / "lib" / "features" / "home" / "presentation" / "bloc",
        project_path / "lib" / "features" / "home" / "data" / "models",
        project_path / "assets" / "svgs",
        project_path / "assets" / "images",
        project_path / "assets" / "sounds",
        project_path / "assets" / "animations",
    ]
    for d in dirs_to_make:
        d.mkdir(parents=True, exist_ok=True)

    # Copy assets if provided
    if assets_src_dir and assets_src_dir.exists():
        print(f"[*] Copying assets from {assets_src_dir} into {project_path}/assets/...")
        for category in ("svgs", "images", "sounds", "animations"):
            src_cat = assets_src_dir / category
            dst_cat = project_path / "assets" / category
            if src_cat.exists():
                for item in src_cat.iterdir():
                    if item.is_file():
                        shutil.copy2(item, dst_cat / item.name)

    # Update pubspec.yaml assets declaration
    pubspec = project_path / "pubspec.yaml"
    pub_content = pubspec.read_text(encoding="utf-8")
    asset_declaration = """
  assets:
    - assets/svgs/
    - assets/images/
    - assets/sounds/
    - assets/animations/
"""
    if "assets:" not in pub_content:
        # Find 'flutter:' block
        pub_content = pub_content.replace("flutter:\n", f"flutter:\n{asset_declaration}")
        pubspec.write_text(pub_content, encoding="utf-8")

    # Generate design system and template files
    (project_path / "lib" / "core" / "theme" / "app_colors.dart").write_text(COLORS_DART_TEMPLATE, encoding="utf-8")
    (project_path / "lib" / "core" / "theme" / "app_theme.dart").write_text(THEME_DART_TEMPLATE, encoding="utf-8")
    (project_path / "lib" / "main.dart").write_text(MAIN_DART_TEMPLATE, encoding="utf-8")
    (project_path / "lib" / "features" / "home" / "presentation" / "views" / "home_screen.dart").write_text(HOME_SCREEN_TEMPLATE, encoding="utf-8")

    print(f"[+] Flutter project successfully scaffolded at: {project_path}")

def main():
    parser = argparse.ArgumentParser(description="Scaffold production-grade Flutter replica project")
    parser.add_argument("name", help="Name of Flutter project (e.g. jaib_flutter_ui)")
    parser.add_argument("--dir", "-d", default=".", help="Parent directory")
    parser.add_argument("--assets", "-a", default=None, help="Directory of extracted assets")
    args = parser.parse_args()

    scaffold_flutter_app(args.name, Path(args.dir), Path(args.assets) if args.assets else None)

if __name__ == "__main__":
    main()
