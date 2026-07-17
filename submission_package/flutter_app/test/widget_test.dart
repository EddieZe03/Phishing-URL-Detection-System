import 'package:flutter_test/flutter_test.dart';
import 'package:phish_guard/main.dart';

void main() {
  testWidgets('Home screen renders primary scan actions',
      (WidgetTester tester) async {
    await tester.pumpWidget(const PhishGuardApp());
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Scan URL'), findsOneWidget);
    expect(find.text('Scan QR Code'), findsOneWidget);
  });
}
