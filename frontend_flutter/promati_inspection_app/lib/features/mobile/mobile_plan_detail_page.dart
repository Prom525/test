import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

class MobilePlanDetailPage extends StatefulWidget {
  final String planId;
  final String userId;
  final String deviceId;

  const MobilePlanDetailPage({
    super.key,
    required this.planId,
    required this.userId,
    required this.deviceId,
  });

  @override
  State<MobilePlanDetailPage> createState() => _MobilePlanDetailPageState();
}

class _MobilePlanDetailPageState extends State<MobilePlanDetailPage> {
  late Future<MobilePlanDetail> planFuture;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    planFuture = loadPlan();
  }

  Future<MobilePlanDetail> loadPlan() async {
    final uri = Uri.parse(
      'http://localhost:8000/planner/mobile-download/inspection-plans/${widget.planId}',
    );

    final response = await http.get(uri).timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) {
      throw Exception(
        'Plan ophalen mislukt: HTTP ${response.statusCode} ${response.body}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return MobilePlanDetail.fromJson(data);
  }

  void refresh() {
    setState(() {
      planFuture = loadPlan();
    });
  }

  Future<void> markDownloaded() async {
    setState(() {
      busy = true;
    });

    try {
      final uri = Uri.parse(
        'http://localhost:8000/planner/mobile-download/inspection-plans/${widget.planId}/downloaded',
      );

      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'user_id': widget.userId,
              'device_id': widget.deviceId,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode != 200) {
        throw Exception(
          'Downloadmelding mislukt: HTTP ${response.statusCode} ${response.body}',
        );
      }

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Plan gemarkeerd als gedownload.')),
      );

      refresh();
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Fout: $e')));
    } finally {
      if (mounted) {
        setState(() {
          busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<MobilePlanDetail>(
      future: planFuture,
      builder: (context, snapshot) {
        final title = snapshot.data == null
            ? 'Inspectieplan'
            : 'Inspectieplan ${snapshot.data!.planDate}';

        return Scaffold(
          appBar: AppBar(
            title: Text(title),
            actions: [
              IconButton(
                onPressed: refresh,
                icon: const Icon(Icons.refresh),
                tooltip: 'Vernieuwen',
              ),
            ],
          ),
          body: _buildBody(snapshot),
        );
      },
    );
  }

  Widget _buildBody(AsyncSnapshot<MobilePlanDetail> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Center(child: CircularProgressIndicator());
    }

    if (snapshot.hasError) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: SelectableText(snapshot.error.toString()),
        ),
      );
    }

    final plan = snapshot.data;

    if (plan == null) {
      return const Center(child: Text('Geen plan gevonden.'));
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _PlanHeader(plan: plan),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Wrap(
              spacing: 12,
              runSpacing: 12,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                FilledButton.icon(
                  onPressed: busy ? null : markDownloaded,
                  icon: const Icon(Icons.download_done),
                  label: const Text('Markeer als gedownload'),
                ),
                if (busy)
                  const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text('Inspectie-items', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        for (final item in plan.items) ...[
          _PlanItemCard(item: item),
          const SizedBox(height: 12),
        ],
      ],
    );
  }
}

class MobilePlanDetail {
  final Map<String, dynamic> plan;
  final List<Map<String, dynamic>> items;

  const MobilePlanDetail({required this.plan, required this.items});

  factory MobilePlanDetail.fromJson(Map<String, dynamic> json) {
    return MobilePlanDetail(
      plan: _map(json['plan']),
      items: _mapList(json['items']),
    );
  }

  String get planId => _text(plan['plan_id']);
  String get planDate => _text(plan['plan_date']);
  String get status =>
      _text(plan['status'], fallback: _text(plan['plan_status']));
  String get customerName => _text(plan['customer_name']);
  String get siteName => _text(plan['site_name']);
  String get basisunitCode => _text(plan['basisunit_code']);
  String get subAreaCode => _text(plan['sub_area_code']);
  String get assignedUserName => _text(plan['assigned_user_name']);
}

class _PlanHeader extends StatelessWidget {
  final MobilePlanDetail plan;

  const _PlanHeader({required this.plan});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 32,
          runSpacing: 12,
          children: [
            _InfoBlock(label: 'Klant', value: plan.customerName),
            _InfoBlock(label: 'Locatie', value: plan.siteName),
            _InfoBlock(label: 'Basisunit', value: plan.basisunitCode),
            _InfoBlock(label: 'Sub-area', value: plan.subAreaCode),
            _InfoBlock(label: 'Status', value: plan.status),
            _InfoBlock(label: 'Monteur', value: plan.assignedUserName),
            _InfoBlock(label: 'Plan', value: plan.planId),
          ],
        ),
      ),
    );
  }
}

class _PlanItemCard extends StatelessWidget {
  final Map<String, dynamic> item;

  const _PlanItemCard({required this.item});

  @override
  Widget build(BuildContext context) {
    final titleParts = [
      _text(item['band_code']),
      _text(item['scraper_position']),
      _text(item['scraper_type']),
    ].where((value) => value.isNotEmpty).toList();

    final title = titleParts.isEmpty
        ? _text(item['scope_type'], fallback: 'Inspectie-item')
        : titleParts.join(' - ');

    return Card(
      child: ListTile(
        leading: const Icon(Icons.fact_check),
        title: Text(title),
        subtitle: Text(
          'Lijn: ${_text(item['lijn_code'])}\n'
          'Vorige meshoogte: ${_text(item['previous_meshoogte_mm'])} mm\n'
          'Vorige conditie: ${_text(item['previous_condition_code'])}\n'
          'Planner-notitie: ${_text(item['planner_note'])}',
        ),
        isThreeLine: true,
      ),
    );
  }
}

class _InfoBlock extends StatelessWidget {
  final String label;
  final String value;

  const _InfoBlock({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 220,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.labelMedium),
          const SizedBox(height: 4),
          SelectableText(
            value.isEmpty ? '-' : value,
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }
}

Map<String, dynamic> _map(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) return Map<String, dynamic>.from(value);
  return <String, dynamic>{};
}

List<Map<String, dynamic>> _mapList(dynamic value) {
  if (value is! List) return [];
  return value.map(_map).where((item) => item.isNotEmpty).toList();
}

String _text(dynamic value, {String fallback = ''}) {
  if (value == null) return fallback;
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}
