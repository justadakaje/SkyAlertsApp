import 'package:flutter/material.dart';

import '../domain/backyard_planner.dart';
import 'theme.dart';

class TonightArcChart extends StatelessWidget {
  const TonightArcChart({
    super.key,
    required this.plan,
    this.minAltDeg = 30.0,
    this.height = 170,
  });

  final PlannedTarget plan;
  final double minAltDeg;
  final double height;

  @override
  Widget build(BuildContext context) {
    final samples = plan.samples;
    if (samples.length < 2) {
      return const SizedBox.shrink();
    }
    final isRed = redNightModeNotifier.value;
    final primaryColor = Theme.of(context).colorScheme.primary;
    final mutedColor = isRed ? SkyRedColors.textSecondary : SkyColors.textSecondary;
    final borderColor = isRed ? SkyRedColors.borderSubtle : SkyColors.borderSubtle;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: height,
          width: double.infinity,
          child: CustomPaint(
            painter: _TonightArcPainter(
              samples: samples,
              minAltDeg: minAltDeg,
              primaryColor: primaryColor,
              mutedColor: mutedColor,
              borderColor: borderColor,
              isRed: isRed,
            ),
          ),
        ),
        const SizedBox(height: 6),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              _fmtUtcHm(samples.first.utc),
              style: TextStyle(fontSize: 11, color: mutedColor),
            ),
            Text(
              'Peak ${plan.peakAltDeg.round()}° at ${_fmtUtcHm(plan.bestTimeUtc)} · Moon ${plan.moonSepDeg.round()}°',
              style: TextStyle(fontSize: 11, color: primaryColor, fontWeight: FontWeight.w600),
            ),
            Text(
              _fmtUtcHm(samples.last.utc),
              style: TextStyle(fontSize: 11, color: mutedColor),
            ),
          ],
        ),
      ],
    );
  }

  static String _fmtUtcHm(DateTime utc) {
    final u = utc.toUtc();
    return '${u.hour.toString().padLeft(2, '0')}:${u.minute.toString().padLeft(2, '0')}Z';
  }
}

class _TonightArcPainter extends CustomPainter {
  _TonightArcPainter({
    required this.samples,
    required this.minAltDeg,
    required this.primaryColor,
    required this.mutedColor,
    required this.borderColor,
    required this.isRed,
  });

  final List<NightSample> samples;
  final double minAltDeg;
  final Color primaryColor;
  final Color mutedColor;
  final Color borderColor;
  final bool isRed;

  @override
  void paint(Canvas canvas, Size size) {
    const leftPad = 30.0;
    const rightPad = 8.0;
    const topPad = 10.0;
    const bottomPad = 14.0;
    final w = size.width - leftPad - rightPad;
    final h = size.height - topPad - bottomPad;
    if (w <= 0 || h <= 0) return;

    double xFor(int i) => leftPad + (i / (samples.length - 1)) * w;
    double yFor(double alt) => topPad + (1.0 - (alt.clamp(0.0, 90.0) / 90.0)) * h;

    // Shade dark-sky spans (sunAlt <= -12) and optimal window spans (alt >= minAltDeg)
    final darkPaint = Paint()
      ..color = (isRed ? const Color(0xFF280505) : const Color(0xFF141D2E)).withValues(alpha: 0.7);
    final goodPaint = Paint()
      ..color = primaryColor.withValues(alpha: 0.14);

    final stepW = w / (samples.length - 1);
    for (var i = 0; i < samples.length - 1; i++) {
      final s = samples[i];
      if (s.isDark) {
        final rect = Rect.fromLTWH(xFor(i), topPad, stepW + 0.5, h);
        canvas.drawRect(rect, darkPaint);
        if (s.altDeg >= minAltDeg && s.moonSepDeg >= 20.0) {
          canvas.drawRect(rect, goodPaint);
        }
      }
    }

    // Horizontal gridlines (0, 30, 60, 90)
    final gridPaint = Paint()
      ..color = borderColor
      ..strokeWidth = 1.0;
    for (final alt in [0.0, 30.0, 60.0, 90.0]) {
      final y = yFor(alt);
      canvas.drawLine(Offset(leftPad, y), Offset(leftPad + w, y), gridPaint);
      final tp = TextPainter(
        text: TextSpan(
          text: '${alt.round()}°',
          style: TextStyle(fontSize: 10, color: mutedColor),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y - tp.height / 2));
    }

    // Minimum altitude threshold line
    final threshY = yFor(minAltDeg);
    final threshPaint = Paint()
      ..color = primaryColor.withValues(alpha: 0.55)
      ..strokeWidth = 1.2;
    canvas.drawLine(Offset(leftPad, threshY), Offset(leftPad + w, threshY), threshPaint);

    // Target altitude curve
    final curvePath = Path();
    var started = false;
    var peakIdx = 0;
    var peakAlt = -90.0;
    for (var i = 0; i < samples.length; i++) {
      final s = samples[i];
      if (s.isDark && s.altDeg > peakAlt) {
        peakAlt = s.altDeg;
        peakIdx = i;
      }
      final pt = Offset(xFor(i), yFor(s.altDeg));
      if (!started) {
        curvePath.moveTo(pt.dx, pt.dy);
        started = true;
      } else {
        curvePath.lineTo(pt.dx, pt.dy);
      }
    }
    final curvePaint = Paint()
      ..color = primaryColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.2
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(curvePath, curvePaint);

    // Peak dot
    if (peakAlt > 0) {
      final peakPt = Offset(xFor(peakIdx), yFor(peakAlt));
      canvas.drawCircle(peakPt, 4.0, Paint()..color = primaryColor);
    }
  }

  @override
  bool shouldRepaint(covariant _TonightArcPainter oldDelegate) {
    return oldDelegate.samples != samples ||
        oldDelegate.minAltDeg != minAltDeg ||
        oldDelegate.primaryColor != primaryColor ||
        oldDelegate.isRed != isRed;
  }
}
