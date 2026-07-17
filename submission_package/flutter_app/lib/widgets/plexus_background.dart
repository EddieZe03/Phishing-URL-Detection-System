import 'dart:math' as math;

import 'package:flutter/material.dart';

class PlexusBackground extends StatelessWidget {
  const PlexusBackground({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return _AnimatedPlexus(child: child);
  }
}

class _AnimatedPlexus extends StatefulWidget {
  const _AnimatedPlexus({required this.child});

  final Widget child;

  @override
  State<_AnimatedPlexus> createState() => _AnimatedPlexusState();
}

class _AnimatedPlexusState extends State<_AnimatedPlexus>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 14),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        return Stack(
          fit: StackFit.expand,
          children: [
            Container(
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    Color(0xFF010528),
                    Color(0xFF030D4F),
                    Color(0xFF004B8E),
                  ],
                ),
              ),
            ),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(-0.78, -0.64),
                  radius: 0.55,
                  colors: [Color(0x3382E6FF), Colors.transparent],
                ),
              ),
            ),
            const DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  center: Alignment(0.86, 0.72),
                  radius: 0.62,
                  colors: [Color(0x2A57C3FF), Colors.transparent],
                ),
              ),
            ),
            CustomPaint(
              painter: _PlexusPainter(time: _controller.value),
              size: Size.infinite,
            ),
            widget.child,
          ],
        );
      },
    );
  }
}

class _PlexusPainter extends CustomPainter {
  _PlexusPainter({required this.time});

  final double time;

  @override
  void paint(Canvas canvas, Size size) {
    final points = <Offset>[];
    const pointCount = 26;

    for (var i = 0; i < pointCount; i++) {
      final fx = (math.sin((time * 2 * math.pi * 0.7) + i * 1.31) + 1) / 2;
      final fy = (math.cos((time * 2 * math.pi * 0.55) + i * 1.97) + 1) / 2;
      final x = fx * size.width;
      final y = fy * size.height;
      points.add(Offset(x, y));
    }

    for (var i = 0; i < points.length; i++) {
      for (var j = i + 1; j < points.length; j++) {
        final d = (points[i] - points[j]).distance;
        if (d < 150) {
          final alpha = (1 - (d / 150)) * 0.24;
          final linePaint = Paint()
            ..color = const Color(0xFF8DD9FF).withValues(alpha: alpha)
            ..strokeWidth = 1;
          canvas.drawLine(points[i], points[j], linePaint);
        }
      }
    }

    final nodePaint = Paint()..color = const Color(0xFF82E6FF).withValues(alpha: 0.58);
    for (final p in points) {
      canvas.drawCircle(p, 2.6, nodePaint);
    }
  }

  @override
  bool shouldRepaint(covariant _PlexusPainter oldDelegate) =>
      oldDelegate.time != time;
}
