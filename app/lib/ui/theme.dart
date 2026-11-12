import 'package:flutter/material.dart';

import '../domain/classes.dart';

class SkyColors {
  static const Color bgPrimary = Color(0xFF0B0E14);
  static const Color bgSurface = Color(0xFF121722);
  static const Color bgElevated = Color(0xFF1A2130);
  static const Color borderSubtle = Color(0xFF263044);
  static const Color textPrimary = Color(0xFFE6EDF3);
  static const Color textSecondary = Color(0xFF9BA7B8);
  static const Color accentAmber = Color(0xFFF5A623);

  static Color forGroup(ClassGroup group) {
    switch (group) {
      case ClassGroup.transients:
        return const Color(0xFFFF6B4A);
      case ClassGroup.variables:
        return const Color(0xFF4DA3FF);
      case ClassGroup.agn:
        return const Color(0xFFB388FF);
      case ClassGroup.solar:
        return const Color(0xFF3DDC97);
      case ClassGroup.other:
        return const Color(0xFF7D8590);
    }
  }

  static Color forBand(String band) {
    switch (band.toLowerCase()) {
      case 'u':
        return const Color(0xFFA855F7);
      case 'g':
        return const Color(0xFF22C55E);
      case 'r':
        return const Color(0xFFEF4444);
      case 'i':
        return const Color(0xFFF59E0B);
      case 'z':
        return const Color(0xFFEC4899);
      case 'y':
        return const Color(0xFF94A3B8);
      default:
        return const Color(0xFF60A5FA);
    }
  }
}

ThemeData buildSkyAlertsTheme() {
  return ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: SkyColors.bgPrimary,
    colorScheme: const ColorScheme.dark(
      primary: SkyColors.accentAmber,
      secondary: Color(0xFF4DA3FF),
      surface: SkyColors.bgSurface,
      onSurface: SkyColors.textPrimary,
    ),
    cardTheme: CardThemeData(
      color: SkyColors.bgSurface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: SkyColors.borderSubtle),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: SkyColors.bgPrimary,
      foregroundColor: SkyColors.textPrimary,
      elevation: 0,
      centerTitle: false,
    ),
    dividerColor: SkyColors.borderSubtle,
  );
}
