import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../domain/astro.dart';
import '../domain/format.dart';
import 'theme.dart';

/// Renders an astronomical deep-sky color CCD cutout (Legacy Survey DR10 -> SDSS DR18 -> Starfield reticle).
class SkyCutoutThumbnail extends StatelessWidget {
  const SkyCutoutThumbnail({
    super.key,
    required this.ra,
    required this.dec,
    this.width = 88,
    this.height = 88,
    this.pixscale = 0.35,
    this.title,
    this.allowLightbox = true,
  });

  final double? ra;
  final double? dec;
  final double width;
  final double height;
  final double pixscale;
  final String? title;
  final bool allowLightbox;

  @override
  Widget build(BuildContext context) {
    final primaryUrl = legacySurveyCutoutUrl(ra, dec, pixscale: pixscale, size: 240);
    final fallbackUrl = sdssCutoutUrl(ra, dec, scale: pixscale, size: 240);

    Widget content;
    if (primaryUrl == null) {
      content = _StarfieldFallback(ra: ra, dec: dec, width: width, height: height);
    } else {
      content = Stack(
        fit: StackFit.expand,
        children: [
          Image.network(
            primaryUrl,
            width: width,
            height: height,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) {
              if (fallbackUrl != null) {
                return Image.network(
                  fallbackUrl,
                  width: width,
                  height: height,
                  fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => _StarfieldFallback(
                    ra: ra,
                    dec: dec,
                    width: width,
                    height: height,
                  ),
                );
              }
              return _StarfieldFallback(ra: ra, dec: dec, width: width, height: height);
            },
          ),
          IgnorePointer(
            child: CustomPaint(
              painter: _ReticleOverlayPainter(),
            ),
          ),
          if (allowLightbox)
            Positioned(
              right: 4,
              bottom: 4,
              child: Container(
                padding: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.65),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: const Icon(
                  Icons.zoom_out_map,
                  size: 12,
                  color: SkyColors.textPrimary,
                ),
              ),
            ),
        ],
      );
    }

    final clipped = ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: SizedBox(width: width, height: height, child: content),
    );

    if (!allowLightbox || primaryUrl == null) return clipped;
    return GestureDetector(
      onTap: () => showCutoutLightbox(
        context,
        title: title ?? 'Sky Cutout (${formatRa(ra)} ${formatDec(dec)})',
        imageUrl: primaryUrl,
        fallbackUrl: fallbackUrl,
        subtitle: 'DESI Legacy Imaging Surveys DR10 / SDSS DR18 · J2000 ${formatRa(ra)} ${formatDec(dec)}',
      ),
      child: clipped,
    );
  }
}

void showCutoutLightbox(
  BuildContext context, {
  required String title,
  required String imageUrl,
  String? fallbackUrl,
  String? subtitle,
}) {
  showDialog<void>(
    context: context,
    builder: (ctx) => Dialog(
      backgroundColor: SkyColors.bgSurface,
      insetPadding: const EdgeInsets.all(16),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 640, maxHeight: 720),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      title,
                      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.of(ctx).pop(),
                    icon: const Icon(Icons.close),
                  ),
                ],
              ),
              if (subtitle != null) ...[
                Text(
                  subtitle,
                  style: const TextStyle(fontSize: 12, color: SkyColors.textSecondary),
                ),
                const SizedBox(height: 12),
              ],
              Flexible(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: InteractiveViewer(
                    minScale: 0.8,
                    maxScale: 5.0,
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        Image.network(
                          imageUrl,
                          fit: BoxFit.contain,
                          errorBuilder: (_, __, ___) => fallbackUrl != null
                              ? Image.network(fallbackUrl, fit: BoxFit.contain)
                              : const SizedBox(
                                  height: 280,
                                  child: Center(child: Text('Cutout image unavailable')),
                                ),
                        ),
                        IgnorePointer(
                          child: SizedBox(
                            width: 280,
                            height: 280,
                            child: CustomPaint(painter: _ReticleOverlayPainter()),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Pinch or scroll to zoom · Crosshair marks J2000 target coordinates.',
                style: TextStyle(fontSize: 11, color: SkyColors.textSecondary),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}

class _StarfieldFallback extends StatelessWidget {
  const _StarfieldFallback({
    required this.ra,
    required this.dec,
    required this.width,
    required this.height,
  });

  final double? ra;
  final double? dec;
  final double width;
  final double height;

  @override
  Widget build(BuildContext context) {
    final seed = ((ra ?? 12.34) * 1000 + (dec ?? -45.6) * 100).round();
    return CustomPaint(
      size: Size(width, height),
      painter: _ProceduralStarfieldPainter(seed: seed),
    );
  }
}

class _ProceduralStarfieldPainter extends CustomPainter {
  const _ProceduralStarfieldPainter({required this.seed});

  final int seed;

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()
      ..shader = const RadialGradient(
        colors: [Color(0xFF1A253A), Color(0xFF090D16)],
      ).createShader(Offset.zero & size);
    canvas.drawRect(Offset.zero & size, bg);

    final rng = math.Random(seed);
    for (var i = 0; i < 28; i++) {
      final x = rng.nextDouble() * size.width;
      final y = rng.nextDouble() * size.height;
      final r = 0.6 + rng.nextDouble() * 1.4;
      final alpha = 0.25 + rng.nextDouble() * 0.7;
      canvas.drawCircle(
        Offset(x, y),
        r,
        Paint()..color = Colors.white.withValues(alpha: alpha),
      );
    }

    final cx = size.width / 2;
    final cy = size.height / 2;
    canvas.drawCircle(
      Offset(cx, cy),
      3.5,
      Paint()..color = SkyColors.accentAmber.withValues(alpha: 0.9),
    );
    const _ReticleOverlayPainter().paint(canvas, size);
  }

  @override
  bool shouldRepaint(covariant _ProceduralStarfieldPainter oldDelegate) =>
      oldDelegate.seed != seed;
}

class _ReticleOverlayPainter extends CustomPainter {
  const _ReticleOverlayPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final cy = size.height / 2;
    final p = Paint()
      ..color = SkyColors.accentAmber.withValues(alpha: 0.75)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;

    canvas.drawLine(Offset(cx - 12, cy), Offset(cx - 4, cy), p);
    canvas.drawLine(Offset(cx + 4, cy), Offset(cx + 12, cy), p);
    canvas.drawLine(Offset(cx, cy - 12), Offset(cx, cy - 4), p);
    canvas.drawLine(Offset(cx, cy + 4), Offset(cx, cy + 12), p);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Interactive Weekly Sky Dispatch Audio Briefing & Editorial Sheet.
void showSkyDispatchSheet(
  BuildContext context, {
  required String subject,
  required String podcastScript,
  required String markdownDispatch,
}) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: SkyColors.bgSurface,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
    ),
    builder: (ctx) => DraggableScrollableSheet(
      initialChildSize: 0.82,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (_, scrollController) => _SkyDispatchSheetBody(
        subject: subject,
        podcastScript: podcastScript,
        markdownDispatch: markdownDispatch,
        scrollController: scrollController,
      ),
    ),
  );
}

class _SkyDispatchSheetBody extends StatefulWidget {
  const _SkyDispatchSheetBody({
    required this.subject,
    required this.podcastScript,
    required this.markdownDispatch,
    required this.scrollController,
  });

  final String subject;
  final String podcastScript;
  final String markdownDispatch;
  final ScrollController scrollController;

  @override
  State<_SkyDispatchSheetBody> createState() => _SkyDispatchSheetBodyState();
}

class _SkyDispatchSheetBodyState extends State<_SkyDispatchSheetBody> {
  bool _playing = false;
  int _activeTurn = 0;
  bool _showMarkdown = false;
  Timer? _timer;
  late final List<({String speaker, String text})> _turns;

  @override
  void initState() {
    super.initState();
    _turns = _parseTurns(widget.podcastScript);
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  List<({String speaker, String text})> _parseTurns(String raw) {
    final lines = raw.split('\n');
    final out = <({String speaker, String text})>[];
    for (final line in lines) {
      final trimmed = line.trim();
      if (trimmed.isEmpty || trimmed.startsWith('#')) continue;
      final colonIdx = trimmed.indexOf(':');
      if (colonIdx > 0 && colonIdx < 18) {
        final speaker = trimmed.substring(0, colonIdx).replaceAll('*', '').trim();
        final text = trimmed.substring(colonIdx + 1).trim();
        if (text.isNotEmpty) {
          out.add((speaker: speaker, text: text));
        }
      } else {
        out.add((speaker: 'Narrator', text: trimmed));
      }
    }
    if (out.isEmpty) {
      out.add((speaker: 'Sky Dispatch', text: raw.isEmpty ? 'No dispatch script generated yet.' : raw));
    }
    return out;
  }

  void _togglePlay() {
    setState(() => _playing = !_playing);
    _timer?.cancel();
    if (_playing) {
      _scheduleNextTurn();
    }
  }

  void _scheduleNextTurn() {
    if (!_playing || _turns.isEmpty) return;
    final words = _turns[_activeTurn].text.split(RegExp(r'\s+')).length;
    final seconds = (words / 2.8).round().clamp(3, 12);
    _timer = Timer(Duration(seconds: seconds), () {
      if (!mounted || !_playing) return;
      setState(() {
        if (_activeTurn < _turns.length - 1) {
          _activeTurn++;
          _scheduleNextTurn();
        } else {
          _playing = false;
        }
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: SkyColors.borderSubtle,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              const Icon(Icons.podcasts, color: SkyColors.accentAmber),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  widget.subject,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ),
              IconButton(
                tooltip: 'Copy dispatch transcript',
                onPressed: () {
                  Clipboard.setData(
                    ClipboardData(
                      text: _showMarkdown ? widget.markdownDispatch : widget.podcastScript,
                    ),
                  );
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Copied Sky Dispatch to clipboard.')),
                  );
                },
                icon: const Icon(Icons.copy_outlined, size: 18),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: SkyColors.bgElevated,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: SkyColors.borderSubtle),
            ),
            child: Row(
              children: [
                FilledButton.icon(
                  onPressed: _togglePlay,
                  icon: Icon(_playing ? Icons.pause : Icons.play_arrow),
                  label: Text(_playing ? 'Pause Briefing' : 'Play Teleprompter'),
                ),
                const SizedBox(width: 8),
                IconButton(
                  tooltip: 'Previous segment',
                  onPressed: _activeTurn > 0
                      ? () => setState(() => _activeTurn--)
                      : null,
                  icon: const Icon(Icons.skip_previous),
                ),
                IconButton(
                  tooltip: 'Next segment',
                  onPressed: _activeTurn < _turns.length - 1
                      ? () => setState(() => _activeTurn++)
                      : null,
                  icon: const Icon(Icons.skip_next),
                ),
                const Spacer(),
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Podcast')),
                    ButtonSegment(value: true, label: Text('Article')),
                  ],
                  selected: {_showMarkdown},
                  onSelectionChanged: (s) => setState(() => _showMarkdown = s.first),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: _showMarkdown
                ? SingleChildScrollView(
                    controller: widget.scrollController,
                    child: SelectableText(
                      widget.markdownDispatch,
                      style: const TextStyle(fontSize: 14, height: 1.55),
                    ),
                  )
                : ListView.builder(
                    controller: widget.scrollController,
                    itemCount: _turns.length,
                    itemBuilder: (_, idx) {
                      final turn = _turns[idx];
                      final isActive = idx == _activeTurn;
                      final isHostA = turn.speaker.toLowerCase().contains('alex') ||
                          turn.speaker.toLowerCase().contains('host 1') ||
                          idx.isEven;
                      final badgeColor = isHostA
                          ? const Color(0xFF38BDF8)
                          : SkyColors.accentAmber;
                      return GestureDetector(
                        onTap: () => setState(() => _activeTurn = idx),
                        child: AnimatedContainer(
                          duration: const Duration(milliseconds: 220),
                          margin: const EdgeInsets.only(bottom: 10),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: isActive
                                ? badgeColor.withValues(alpha: 0.14)
                                : SkyColors.bgPrimary,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isActive ? badgeColor : SkyColors.borderSubtle,
                              width: isActive ? 1.5 : 1.0,
                            ),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(
                                    isHostA ? Icons.graphic_eq : Icons.mic_none,
                                    size: 15,
                                    color: badgeColor,
                                  ),
                                  const SizedBox(width: 6),
                                  Text(
                                    turn.speaker.toUpperCase(),
                                    style: TextStyle(
                                      fontSize: 11,
                                      fontWeight: FontWeight.bold,
                                      letterSpacing: 0.9,
                                      color: badgeColor,
                                    ),
                                  ),
                                  const Spacer(),
                                  Text(
                                    '${idx + 1}/${_turns.length}',
                                    style: const TextStyle(
                                      fontSize: 11,
                                      color: SkyColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 6),
                              Text(
                                turn.text,
                                style: TextStyle(
                                  fontSize: 14,
                                  height: 1.45,
                                  color: isActive
                                      ? SkyColors.textPrimary
                                      : SkyColors.textSecondary,
                                ),
                              ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}
