import 'package:flutter_test/flutter_test.dart';

import 'package:promati_inspection_app/main.dart';

void main() {
  testWidgets('PROMATI startscherm toont hoofdmodules', (tester) async {
    await tester.pumpWidget(const PromatiInspectionApp());

    expect(find.text('PROMATI Inspectieplatform'), findsOneWidget);
    expect(find.text('Monteur app'), findsOneWidget);
    expect(find.text('Planner'), findsOneWidget);
    expect(find.text('Validatie'), findsOneWidget);
  });
}
