import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:uuid/uuid.dart';

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
  final Map<String, _InspectionItemFormState> itemForms = {};
  final Uuid uuid = const Uuid();
  bool busy = false;

  @override
  void initState() {
    super.initState();
    planFuture = loadPlan();
  }

  @override
  void dispose() {
    for (final form in itemForms.values) {
      form.dispose();
    }
    super.dispose();
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

  void ensureForms(MobilePlanDetail plan) {
    for (final item in plan.items) {
      final key = _itemKey(item);

      itemForms.putIfAbsent(
        key,
        () => _InspectionItemFormState(
          meshoogteText: '',
          conditionCode: _text(item['previous_condition_code'], fallback: 'OK'),
          status: 'OK',
          severity: 'LOW',
          opmerking: '',
        ),
      );
    }
  }

  Future<void> submitInspection(MobilePlanDetail plan) async {
    final now = DateTime.now().toUtc().toIso8601String();
    final submissionItems = <Map<String, dynamic>>[];

    for (final item in plan.items) {
      final form = itemForms[_itemKey(item)];

      if (form == null) {
        continue;
      }

      final meshoogteText = form.meshoogteController.text.trim().replaceAll(
        ',',
        '.',
      );
      final meshoogte = meshoogteText.isEmpty
          ? null
          : double.tryParse(meshoogteText);

      if (meshoogteText.isNotEmpty && meshoogte == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              'Meshoogte is ongeldig bij ${_text(item['band_code'])}. Gebruik bijvoorbeeld 4.2',
            ),
          ),
        );
        return;
      }

      submissionItems.add({
        'client_item_id': uuid.v4(),
        'plan_item_id': _nullIfEmpty(_text(item['plan_item_id'])),
        'scope_type': _text(item['scope_type'], fallback: 'SCRAPER_POSITION'),
        'lijn_code': _nullIfEmpty(_text(item['lijn_code'])),
        'band_code': _nullIfEmpty(_text(item['band_code'])),
        'side': _nullIfEmpty(_text(item['side'])),
        'component_type': _nullIfEmpty(_text(item['component_type'])),
        'transfer_point_id': _nullIfEmpty(_text(item['transfer_point_id'])),
        'scraper_position_id': _nullIfEmpty(_text(item['scraper_position_id'])),
        'scraper_position': _nullIfEmpty(_text(item['scraper_position'])),
        'scraper_role': _nullIfEmpty(_text(item['scraper_role'])),
        'scraper_type': _nullIfEmpty(_text(item['scraper_type'])),
        'scraper_family': _nullIfEmpty(_text(item['scraper_family'])),
        'measurement_type': 'MESHOOGTE',
        'measurement_value_num': meshoogte,
        'measurement_value_text': meshoogte?.toString(),
        'meshoogte_mm': meshoogte,
        'condition_code': _nullIfEmpty(form.conditionController.text.trim()),
        'status': _nullIfEmpty(form.statusController.text.trim()),
        'severity': _nullIfEmpty(form.severityController.text.trim()),
        'opmerking': _nullIfEmpty(form.opmerkingController.text.trim()),
        'action_required': form.actionRequired,
        'replaced': form.replaced,
        'asset_match_status': 'MATCHED',
        'offline_created_at': now,
        'raw_payload': {
          'source': 'flutter_monteur_flow_item',
          'planner_note': _text(item['planner_note']),
        },
      });
    }

    if (submissionItems.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Er zijn geen inspectie-items om te synchroniseren.'),
        ),
      );
      return;
    }

    setState(() {
      busy = true;
    });

    try {
      final uri = Uri.parse(
        'http://localhost:8000/mobile/inspection-submissions',
      );

      final payload = {
        'client_submission_id': uuid.v4(),
        'plan_id': _nullIfEmpty(plan.planId),
        'user_id': widget.userId,
        'user_name': _nullIfEmpty(plan.assignedUserName),
        'device_id': widget.deviceId,
        'customer_id': _nullIfEmpty(plan.customerId),
        'customer_name': _nullIfEmpty(plan.customerName),
        'site_id': _nullIfEmpty(plan.siteId),
        'site_name': _nullIfEmpty(plan.siteName),
        'basisunit_code': _nullIfEmpty(plan.basisunitCode),
        'sub_area_code': _nullIfEmpty(plan.subAreaCode),
        'offline_started_at': now,
        'offline_completed_at': now,
        'raw_payload': {
          'source': 'flutter_monteur_flow',
          'plan_status_at_submit': plan.status,
        },
        'items': submissionItems,
      };

      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode != 200) {
        throw Exception(
          'Synchronisatie mislukt: HTTP ${response.statusCode} ${response.body}',
        );
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;

      if (!mounted) return;

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            'Inspectie gesynchroniseerd. Status: ${data['validation_status']}.',
          ),
        ),
      );

      Navigator.of(context).pop();
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

    ensureForms(plan);

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
                FilledButton.icon(
                  onPressed: busy ? null : () => submitInspection(plan),
                  icon: const Icon(Icons.cloud_upload),
                  label: const Text('Synchroniseer inspectie'),
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
          _InspectionItemFormCard(
            item: item,
            form: itemForms[_itemKey(item)]!,
            onChanged: () => setState(() {}),
          ),
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
  String get customerId => _text(plan['customer_id']);
  String get customerName => _text(plan['customer_name']);
  String get siteId => _text(plan['site_id']);
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

class _InspectionItemFormCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final _InspectionItemFormState form;
  final VoidCallback onChanged;

  const _InspectionItemFormCard({
    required this.item,
    required this.form,
    required this.onChanged,
  });

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
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        initiallyExpanded: true,
        tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
        childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        leading: const Icon(Icons.fact_check),
        title: Text(title, style: Theme.of(context).textTheme.titleMedium),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            'Lijn: ${_text(item['lijn_code'])}  |  '
            'Vorige meshoogte: ${_text(item['previous_meshoogte_mm'])} mm  |  '
            'Vorige conditie: ${_text(item['previous_condition_code'])}',
          ),
        ),
        children: [
          if (_text(item['planner_note']).isNotEmpty) ...[
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Theme.of(
                  context,
                ).colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.notes, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _text(item['planner_note']),
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],
          Align(
            alignment: Alignment.centerLeft,
            child: Wrap(
              alignment: WrapAlignment.start,
              crossAxisAlignment: WrapCrossAlignment.start,
              spacing: 12,
              runSpacing: 12,
              children: [
                SizedBox(
                  width: 180,
                  child: TextField(
                    controller: form.meshoogteController,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: const InputDecoration(
                      labelText: 'Meshoogte mm',
                      hintText: 'bijv. 4.2',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                SizedBox(
                  width: 160,
                  child: TextField(
                    controller: form.conditionController,
                    decoration: const InputDecoration(
                      labelText: 'Conditie',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                SizedBox(
                  width: 160,
                  child: TextField(
                    controller: form.statusController,
                    decoration: const InputDecoration(
                      labelText: 'Status',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                SizedBox(
                  width: 160,
                  child: TextField(
                    controller: form.severityController,
                    decoration: const InputDecoration(
                      labelText: 'Severity',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          TextField(
            controller: form.opmerkingController,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'Opmerking',
              hintText: 'Bijzonderheden, schade, vervuiling of advies...',
              border: OutlineInputBorder(),
              alignLabelWithHint: true,
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                FilterChip(
                  avatar: form.actionRequired
                      ? const Icon(Icons.priority_high, size: 18)
                      : null,
                  label: const Text('Actie nodig'),
                  selected: form.actionRequired,
                  onSelected: (value) {
                    form.actionRequired = value;
                    onChanged();
                  },
                ),
                FilterChip(
                  avatar: form.replaced
                      ? const Icon(Icons.check, size: 18)
                      : null,
                  label: const Text('Vervangen'),
                  selected: form.replaced,
                  onSelected: (value) {
                    form.replaced = value;
                    onChanged();
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InspectionItemFormState {
  final TextEditingController meshoogteController;
  final TextEditingController conditionController;
  final TextEditingController statusController;
  final TextEditingController severityController;
  final TextEditingController opmerkingController;

  bool actionRequired = false;
  bool replaced = false;

  _InspectionItemFormState({
    required String meshoogteText,
    required String conditionCode,
    required String status,
    required String severity,
    required String opmerking,
  }) : meshoogteController = TextEditingController(text: meshoogteText),
       conditionController = TextEditingController(text: conditionCode),
       statusController = TextEditingController(text: status),
       severityController = TextEditingController(text: severity),
       opmerkingController = TextEditingController(text: opmerking);

  void dispose() {
    meshoogteController.dispose();
    conditionController.dispose();
    statusController.dispose();
    severityController.dispose();
    opmerkingController.dispose();
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

String _itemKey(Map<String, dynamic> item) {
  final planItemId = _text(item['plan_item_id']);
  if (planItemId.isNotEmpty) return planItemId;

  final fallbackParts = [
    _text(item['band_code']),
    _text(item['scraper_position_id']),
    _text(item['scraper_type']),
  ].where((value) => value.isNotEmpty).toList();

  return fallbackParts.isEmpty
      ? item.hashCode.toString()
      : fallbackParts.join('|');
}

String? _nullIfEmpty(String value) {
  final text = value.trim();

  if (text.isEmpty || text == '-') {
    return null;
  }

  return text;
}

String _text(dynamic value, {String fallback = ''}) {
  if (value == null) return fallback;
  final text = value.toString().trim();
  return text.isEmpty ? fallback : text;
}
