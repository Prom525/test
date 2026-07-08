import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class MobilePlansPage extends StatefulWidget {
  const MobilePlansPage({super.key});

  @override
  State<MobilePlansPage> createState() => _MobilePlansPageState();
}

class _MobilePlansPageState extends State<MobilePlansPage> {
  final TextEditingController userIdController =
      TextEditingController(text: 'monteur-test');

  late Future<List<MobilePlanSummary>> plansFuture;

  @override
  void initState() {
    super.initState();
    plansFuture = loadPlans();
  }

  @override
  void dispose() {
    userIdController.dispose();
    super.dispose();
  }

  Future<List<MobilePlanSummary>> loadPlans() async {
    final userId = userIdController.text.trim();

    final uri = Uri.parse(
      'http://localhost:8000/planner/mobile-download/inspection-plans',
    ).replace(
      queryParameters: {
        'assigned_user_id': userId,
        'limit': '50',
      },
    );

    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) {
      throw Exception(
        'Planning ophalen mislukt: HTTP ${response.statusCode} ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    final rawResults = data['results'];

    if (rawResults is! List) {
      return [];
    }

    return rawResults
        .whereType<Map<String, dynamic>>()
        .map(MobilePlanSummary.fromJson)
        .toList();
  }

  void refresh() {
    setState(() {
      plansFuture = loadPlans();
    });
  }

  void openPlan(MobilePlanSummary plan) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Plan openen komt in fase M2: ${plan.planId}'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Monteur app'),
        actions: [
          IconButton(
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Planning vernieuwen',
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  children: [
                    Expanded(
                      child: TextField(
                        controller: userIdController,
                        decoration: const InputDecoration(
                          labelText: 'Monteur user_id',
                          helperText: 'Voor test gebruiken we: monteur-test',
                          border: OutlineInputBorder(),
                        ),
                        onSubmitted: (_) => refresh(),
                      ),
                    ),
                    const SizedBox(width: 12),
                    FilledButton.icon(
                      onPressed: refresh,
                      icon: const Icon(Icons.search),
                      label: const Text('Ophalen'),
                    ),
                  ],
                ),
              ),
            ),
          ),
          Expanded(
            child: FutureBuilder<List<MobilePlanSummary>>(
              future: plansFuture,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }

                if (snapshot.hasError) {
                  return _ErrorView(
                    message: snapshot.error.toString(),
                    onRetry: refresh,
                  );
                }

                final plans = snapshot.data ?? [];

                if (plans.isEmpty) {
                  return const Center(
                    child: Padding(
                      padding: EdgeInsets.all(24),
                      child: Text(
                        'Geen gepubliceerde inspectieplannen gevonden.\n\n'
                        'Maak of publiceer eerst een testplan voor monteur-test.',
                        textAlign: TextAlign.center,
                      ),
                    ),
                  );
                }

                return ListView.separated(
                  padding: const EdgeInsets.all(16),
                  itemCount: plans.length,
                  separatorBuilder: (_, index) => const SizedBox(height: 12),
                  itemBuilder: (context, index) {
                    final plan = plans[index];

                    return Card(
                      child: ListTile(
                        onTap: () => openPlan(plan),
                        leading: const Icon(Icons.assignment),
                        title: Text('Inspectieplan ${plan.planDate}'),
                        subtitle: Text(
                          'Status: ${plan.status}\n'
                          'Items: ${plan.itemCount}\n'
                          'Plan: ${plan.planId}',
                        ),
                        trailing: const Icon(Icons.chevron_right),
                        isThreeLine: true,
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class MobilePlanSummary {
  final String planId;
  final String planDate;
  final String status;
  final int itemCount;

  const MobilePlanSummary({
    required this.planId,
    required this.planDate,
    required this.status,
    required this.itemCount,
  });

  factory MobilePlanSummary.fromJson(Map<String, dynamic> json) {
    return MobilePlanSummary(
      planId: _text(json['plan_id']),
      planDate: _text(json['plan_date']),
      status: _text(json['status'], fallback: _text(json['plan_status'])),
      itemCount: _int(json['item_count']),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({
    required this.message,
    required this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 650),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 48, color: Colors.red),
                const SizedBox(height: 16),
                const Text(
                  'Mobiele planning kon niet geladen worden.',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 8),
                SelectableText(message),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: onRetry,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Opnieuw proberen'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

String _text(dynamic value, {String fallback = ''}) {
  if (value == null) return fallback;
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}

int _int(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value) ?? 0;
  return 0;
}