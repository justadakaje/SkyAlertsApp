import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../data/firestore_repository.dart';
import 'admin_screen.dart';
import 'home_screen.dart';
import 'object_detail_screen.dart';
import 'saved_alerts_screen.dart';
import 'solar_system_screen.dart';
import 'theme.dart';
import 'tonight_screen.dart';
import 'trends_screen.dart';

GoRouter buildAppRouter(SkyAlertsRepository repository) {
  return GoRouter(
    initialLocation: '/',
    routes: [
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) {
          return AdaptiveAppShell(navigationShell: navigationShell);
        },
        branches: [
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/',
                builder: (context, state) => HomeScreen(repository: repository),
                routes: [
                  GoRoute(
                    path: 'objects/:survey/:oid',
                    builder: (context, state) => ObjectDetailScreen(
                      repository: repository,
                      survey: state.pathParameters['survey'] ?? 'ztf',
                      oid: state.pathParameters['oid'] ?? '',
                    ),
                  ),
                ],
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/tonight',
                builder: (context, state) => TonightScreen(repository: repository),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/solar-system',
                builder: (context, state) => SolarSystemScreen(repository: repository),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/trends',
                builder: (context, state) => TrendsScreen(repository: repository),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/saved',
                builder: (context, state) => SavedAlertsScreen(repository: repository),
              ),
            ],
          ),
          StatefulShellBranch(
            routes: [
              GoRoute(
                path: '/admin',
                builder: (context, state) => AdminScreen(repository: repository),
              ),
            ],
          ),
        ],
      ),
    ],
  );
}

class AdaptiveAppShell extends StatelessWidget {
  const AdaptiveAppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  void _onTap(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isRed = redNightModeNotifier.value;
        final navBg = isRed ? SkyRedColors.bgSurface : SkyColors.bgSurface;
        final isWide = constraints.maxWidth >= 760;
        if (isWide) {
          return Scaffold(
            body: Row(
              children: [
                NavigationRail(
                  backgroundColor: navBg,
                  selectedIndex: navigationShell.currentIndex,
                  onDestinationSelected: _onTap,
                  labelType: NavigationRailLabelType.all,
                  leading: const Padding(
                    padding: EdgeInsets.symmetric(vertical: 16),
                    child: Icon(Icons.auto_awesome, color: SkyColors.accentAmber, size: 28),
                  ),
                  trailing: Expanded(
                    child: Align(
                      alignment: Alignment.bottomCenter,
                      child: Padding(
                        padding: const EdgeInsets.only(bottom: 16),
                        child: IconButton(
                          onPressed: () => redNightModeNotifier.value = !isRed,
                          tooltip: isRed ? 'Exit Red Night Mode' : 'Red Night Mode (OLED)',
                          icon: Icon(
                            isRed ? Icons.nights_stay : Icons.nights_stay_outlined,
                            color: isRed ? SkyRedColors.accentRed : SkyColors.textSecondary,
                          ),
                        ),
                      ),
                    ),
                  ),
                  destinations: const [
                    NavigationRailDestination(
                      icon: Icon(Icons.explore_outlined),
                      selectedIcon: Icon(Icons.explore),
                      label: Text('Sky Feed'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.visibility_outlined),
                      selectedIcon: Icon(Icons.visibility),
                      label: Text('Tonight'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.public_outlined),
                      selectedIcon: Icon(Icons.public),
                      label: Text('Solar System'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.stacked_line_chart),
                      selectedIcon: Icon(Icons.stacked_line_chart),
                      label: Text('Trends'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.notifications_active_outlined),
                      selectedIcon: Icon(Icons.notifications_active),
                      label: Text('Saved & Alerts'),
                    ),
                    NavigationRailDestination(
                      icon: Icon(Icons.admin_panel_settings_outlined),
                      selectedIcon: Icon(Icons.admin_panel_settings),
                      label: Text('Admin'),
                    ),
                  ],
                ),
                const VerticalDivider(width: 1),
                Expanded(child: navigationShell),
              ],
            ),
          );
        }

        return Scaffold(
          body: navigationShell,
          bottomNavigationBar: NavigationBar(
            backgroundColor: navBg,
            selectedIndex: navigationShell.currentIndex,
            onDestinationSelected: _onTap,
            destinations: const [
              NavigationDestination(icon: Icon(Icons.explore_outlined), label: 'Feed'),
              NavigationDestination(icon: Icon(Icons.visibility_outlined), label: 'Tonight'),
              NavigationDestination(icon: Icon(Icons.public_outlined), label: 'Solar'),
              NavigationDestination(icon: Icon(Icons.stacked_line_chart), label: 'Trends'),
              NavigationDestination(
                icon: Icon(Icons.notifications_active_outlined),
                label: 'Alerts',
              ),
              NavigationDestination(
                icon: Icon(Icons.admin_panel_settings_outlined),
                label: 'Admin',
              ),
            ],
          ),
        );
      },
    );
  }
}
