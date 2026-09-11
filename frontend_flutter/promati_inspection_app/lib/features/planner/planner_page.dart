import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../../config/app_config.dart';

class PlannerPage extends StatefulWidget {
  const PlannerPage({super.key});

  @override
  State<PlannerPage> createState() => _PlannerPageState();
}

class _PlannerPageState extends State<PlannerPage> {
  late Future<List<Map<String, dynamic>>> plansFuture;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    plansFuture = loadPlans();
  }

  Future<List<Map<String, dynamic>>> loadPlans() async {
    final uri = Uri.parse('${AppConfig.apiBaseUrl}/planner/inspection-plans')
        .replace(queryParameters: {'limit': '50'});

    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) {
      throw Exception(
        'Inspectieplannen konden niet geladen worden: HTTP ${response.statusCode} ${response.body}',
      );
    }

    final data = jsonDecode(response.body);

    if (data is List) {
      return data.cast<Map<String, dynamic>>();
    }

    if (data is Map<String, dynamic>) {
      final results = data['results'];
      if (results is List) {
        return results.cast<Map<String, dynamic>>();
      }
    }

    return <Map<String, dynamic>>[];
  }

  void refresh() {
    setState(() {
      plansFuture = loadPlans();
    });
  }

  Future<void> createTestPlan() async {
    setState(() => busy = true);

    try {
      final uri = Uri.parse('${AppConfig.apiBaseUrl}/planner/inspection-plans');

      final planDate = '2026-09-14';

      final items = [
        {
          'scope_type': 'SCRAPER_POSITION',
          'lijn_code': 'MV2',
          'band_code': 'E950',
          'scraper_position': 'Primair',
          'scraper_type': 'R 1200-1050 SP/M3',
          'measurement_type': 'MESHOOGTE',
          'planner_note': 'Controleer primaire schraper E950.',
          'priority': 1,
          'required_photos': false,
        },
        {
          'scope_type': 'SCRAPER_POSITION',
          'lijn_code': 'MV2',
          'band_code': 'E950',
          'scraper_position': 'Secundair',
          'scraper_type': 'R 1200-1050 SP/M3',
          'measurement_type': 'MESHOOGTE',
          'planner_note': 'Controleer secundaire schraper E950.',
          'priority': 1,
          'required_photos': false,
        },
        {
          'scope_type': 'SCRAPER_POSITION',
          'lijn_code': 'MV2',
          'band_code': 'A513',
          'scraper_position': 'U-positie',
          'scraper_type': 'U 1600',
          'measurement_type': 'MESHOOGTE',
          'planner_note': 'Controleer U-positie A513.',
          'priority': 2,
          'required_photos': false,
        },
        {
          'scope_type': 'SCRAPER_POSITION',
          'lijn_code': 'MV2',
          'band_code': 'A513',
          'scraper_position': 'H-positie',
          'scraper_type': 'H 1600',
          'measurement_type': 'MESHOOGTE',
          'planner_note': 'Controleer H-positie A513.',
          'priority': 2,
          'required_photos': false,
        },
        {
          'scope_type': 'SCRAPER_POSITION',
          'lijn_code': 'MV1',
          'band_code': 'S101',
          'scraper_position': 'Primair',
          'scraper_type': 'H 1200-1000 SP/M3',
          'measurement_type': 'MESHOOGTE',
          'planner_note': 'Extra aandacht: vorige meting laag.',
          'priority': 1,
          'required_photos': true,
        },
      ];

      final payload = {
        'plan_date': planDate,
        'customer_id': 'TATA_STEEL',
        'customer_name': 'TATA Steel',
        'site_id': 'IJMUIDEN',
        'site_name': 'IJmuiden',
        'basisunit_code': 'GSL',
        'sub_area_code': 'MV2',
        'assigned_user_id': 'monteur-test',
        'assigned_user_name': 'Test Monteur',
        'created_by': 'planner-test',
        'remarks':
            'Dagplanning 14-09-2026 met meerdere banden en schraperposities.',
        'items': items,
      };

      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(
          'Plan aanmaken mislukt: HTTP ${response.statusCode} ${response.body}',
        );
      }

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Dagplanning aangemaakt: ${items.length} schraperposities.',
          ),
        ),
      );

      refresh();
    } catch (error) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$error')),
      );
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  Future<void> publishPlan(String planId) async {
    setState(() => busy = true);

    try {
      final uri = Uri.parse(
        '${AppConfig.apiBaseUrl}/planner/inspection-plans/$planId/publish',
      );

      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'published_by': 'planner-test',
              'note': 'Gepubliceerd vanuit Flutter planner.',
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw Exception(
          'Publiceren mislukt: HTTP ${response.statusCode} ${response.body}',
        );
      }

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Inspectieplan gepubliceerd.')),
      );

      refresh();
    } catch (error) {
      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('$error')),
      );
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  String textValue(
    Map<String, dynamic> row,
    String key, {
    String fallback = '',
  }) {
    final value = row[key];
    if (value == null) return fallback;
    return value.toString();
  }

  String planIdOf(Map<String, dynamic> row) {
    return textValue(row, 'plan_id', fallback: textValue(row, 'id'));
  }

  bool canPublish(String status) {
    return status != 'PROMOTED' &&
        status != 'PUBLISHED' &&
        status != 'PROMOTED_TO_CANONICAL_DB';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Planner'),
        actions: [
          IconButton(
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Vernieuwen',
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: busy ? null : createTestPlan,
        icon: const Icon(Icons.add),
        label: const Text('Nieuwe dagplanning'),
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: plansFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }

          if (snapshot.hasError) {
            return Center(
              child: Card(
                margin: const EdgeInsets.all(24),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(
                        Icons.error_outline,
                        color: Colors.red,
                        size: 48,
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Planner kon niet geladen worden.',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(height: 8),
                      Text('${snapshot.error}'),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: refresh,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Opnieuw proberen'),
                      ),
                    ],
                  ),
                ),
              ),
            );
          }

          final plans = snapshot.data ?? [];

          if (plans.isEmpty) {
            return const Center(
              child: Text('Geen inspectieplannen gevonden.'),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: plans.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8),
            itemBuilder: (context, index) {
              final plan = plans[index];
              final planId = planIdOf(plan);
              final status = textValue(plan, 'status', fallback: 'ONBEKEND');

              final title = [
                textValue(plan, 'customer_name', fallback: 'Klant'),
                textValue(plan, 'site_name'),
                textValue(plan, 'basisunit_code'),
                textValue(plan, 'sub_area_code'),
              ].where((value) => value.isNotEmpty).join(' - ');

              final planDate = textValue(
                plan,
                'plan_date',
                fallback: textValue(plan, 'date'),
              );

              final monteur = textValue(
                plan,
                'assigned_user_name',
                fallback: textValue(plan, 'assigned_user_id'),
              );

              return Card(
                child: ListTile(
                  leading: const Icon(Icons.calendar_month),
                  title: Text(title),
                  subtitle: Text(
                    'Datum: $planDate\n'
                    'Monteur: $monteur\n'
                    'Status: $status\n'
                    'Plan: $planId',
                  ),
                  isThreeLine: true,
                  trailing: Wrap(
                    spacing: 8,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Chip(label: Text(status)),
                      FilledButton(
                        onPressed: busy || planId.isEmpty || !canPublish(status)
                            ? null
                            : () => publishPlan(planId),
                        child: Text(
                          canPublish(status) ? 'Publiceren' : 'Gepubliceerd',
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}