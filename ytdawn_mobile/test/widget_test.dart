import 'package:flutter_test/flutter_test.dart';
import 'package:ytdawn_mobile/main.dart';

void main() {
  testWidgets('YTDawn smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const YTDawnApp());
    expect(find.text('YTDawn'), findsOneWidget);
  });
}
