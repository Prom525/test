import 'package:flutter/material.dart';

import '../../api/promati_api_client.dart';

class ValidationSubmissionDetailPage extends StatefulWidget {
  final PromatiApiClient apiClient;
  final String submissionId;

  const ValidationSubmissionDetailPage({
    super.key,
    required this.apiClient,
    required this.submissionId,
  });

  @override
  State<ValidationSubmissionDetailPage> createState() =>
      _ValidationSubmissionDetailPageState();
}

class _ValidationSubmissionDetailPageState
    extends State<ValidationSubmissionDetailPage> {
  late Future<ValidationSubmissionDetail> detailFuture;
  bool actionBusy = false;

  @override
  void initState() {
    super.initState();
    detailFuture = widget.apiClient.getValidationSubmission(
      widget.submissionId,
    );
  }

  void refresh() {
    setState(() {
      detailFuture = widget.apiClient.getValidationSubmission(
        widget.submissionId,
      );
    });
  }

  Future<void> runAction(
    String successMessage,
    Future<Map<String, dynamic>> Function() action,
  ) async {
    setState(() {
      actionBusy = true;
    });

    try {
      await action();

      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(successMessage)));

      refresh();
    } catch (e) {
      if (!mounted) return;

      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text('Actie mislukt: $e')));
    } finally {
      if (mounted) {
        setState(() {
          actionBusy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Submission detail'),
        actions: [
          IconButton(
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Vernieuwen',
          ),
        ],
      ),
      body: FutureBuilder<ValidationSubmissionDetail>(
        future: detailFuture,
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

          final detail = snapshot.data;

          if (detail == null) {
            return const Center(child: Text('Geen detaildata gevonden.'));
          }

          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _SubmissionHeader(detail: detail),
              const SizedBox(height: 16),
              _ActionPanel(
                actionBusy: actionBusy,
                detail: detail,
                onStart: () => runAction(
                  'Validatie gestart.',
                  () => widget.apiClient.startValidation(
                    submissionId: detail.submissionId,
                    note: 'Validatie gestart vanuit Flutter app.',
                  ),
                ),
                onApprove: () => runAction(
                  'Submission goedgekeurd.',
                  () => widget.apiClient.approveSubmission(
                    submissionId: detail.submissionId,
                    note: 'Goedgekeurd vanuit Flutter app.',
                  ),
                ),
                onNeedsCorrection: () => runAction(
                  'Submission teruggezet naar correctie.',
                  () => widget.apiClient.needsCorrection(
                    submissionId: detail.submissionId,
                    note: 'Correctie gevraagd vanuit Flutter app.',
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _ItemsSection(items: detail.items),
              const SizedBox(height: 16),
              _IssuesSection(issues: detail.validationIssues),
            ],
          );
        },
      ),
    );
  }
}

class _SubmissionHeader extends StatelessWidget {
  final ValidationSubmissionDetail detail;

  const _SubmissionHeader({required this.detail});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 32,
          runSpacing: 12,
          children: [
            _InfoBlock(label: 'Klant', value: detail.customerDisplay),
            _InfoBlock(label: 'Locatie', value: detail.siteDisplay),
            _InfoBlock(label: 'Monteur', value: detail.userDisplay),
            _InfoBlock(label: 'Status', value: detail.validationStatus),
            _InfoBlock(label: 'Items', value: '${detail.itemCount}'),
            _InfoBlock(label: 'Issues', value: '${detail.issueCount}'),
            _InfoBlock(label: 'Submission', value: detail.submissionId),
          ],
        ),
      ),
    );
  }
}

class _ActionPanel extends StatelessWidget {
  final bool actionBusy;
  final ValidationSubmissionDetail detail;
  final VoidCallback onStart;
  final VoidCallback onApprove;
  final VoidCallback onNeedsCorrection;

  const _ActionPanel({
    required this.actionBusy,
    required this.detail,
    required this.onStart,
    required this.onApprove,
    required this.onNeedsCorrection,
  });

  @override
  Widget build(BuildContext context) {
    final hasIssues = detail.issueCount > 0;
    final canApprove = !hasIssues && detail.itemCount > 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Wrap(
          spacing: 12,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            FilledButton.icon(
              onPressed: actionBusy ? null : onStart,
              icon: const Icon(Icons.play_arrow),
              label: const Text('Start validatie'),
            ),
            FilledButton.icon(
              onPressed: actionBusy || !canApprove ? null : onApprove,
              icon: const Icon(Icons.check),
              label: const Text('Goedkeuren'),
            ),
            OutlinedButton.icon(
              onPressed: actionBusy ? null : onNeedsCorrection,
              icon: const Icon(Icons.edit_note),
              label: const Text('Correctie nodig'),
            ),
            if (actionBusy)
              const SizedBox(
                width: 24,
                height: 24,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            if (!canApprove)
              const Text(
                'Goedkeuren kan alleen zonder issues en met minimaal 1 item.',
              ),
          ],
        ),
      ),
    );
  }
}

class _ItemsSection extends StatelessWidget {
  final List<Map<String, dynamic>> items;

  const _ItemsSection({required this.items});

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.info_outline),
          title: Text('Geen inspectie-items gevonden.'),
        ),
      );
    }

    return Card(
      child: ExpansionTile(
        initiallyExpanded: true,
        title: Text('Inspectie-items (${items.length})'),
        children: [
          for (final item in items)
            ListTile(
              leading: const Icon(Icons.fact_check),
              title: Text(
                [
                  _text(item['scope_type']),
                  _text(item['band_code']),
                  _text(item['scraper_position']),
                ].where((value) => value.isNotEmpty).join(' - '),
              ),
              subtitle: Text(
                'Status: ${_text(item['status'])}\n'
                'Meting: ${_text(item['measurement_type'])} '
                '${_text(item['meshoogte_mm'])}\n'
                'Schraper: ${_text(item['scraper_type'])}\n'
                'Opmerking: ${_text(item['opmerking'])}',
              ),
              isThreeLine: true,
            ),
        ],
      ),
    );
  }
}

class _IssuesSection extends StatelessWidget {
  final List<Map<String, dynamic>> issues;

  const _IssuesSection({required this.issues});

  @override
  Widget build(BuildContext context) {
    if (issues.isEmpty) {
      return const Card(
        child: ListTile(
          leading: Icon(Icons.check_circle, color: Colors.green),
          title: Text('Geen validatieproblemen gevonden.'),
        ),
      );
    }

    return Card(
      child: ExpansionTile(
        initiallyExpanded: true,
        title: Text('Validatieproblemen (${issues.length})'),
        children: [
          for (final issue in issues)
            ListTile(
              leading: const Icon(Icons.warning_amber, color: Colors.orange),
              title: Text(_text(issue['issue_code'])),
              subtitle: Text(
                'Scope: ${_text(issue['issue_scope'])}\n'
                '${_text(issue['issue_message'])}',
              ),
            ),
        ],
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

class _ErrorView extends StatelessWidget {
  final String message;
  final VoidCallback onRetry;

  const _ErrorView({required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: Colors.red),
              const SizedBox(height: 16),
              const Text('Detail kon niet geladen worden.'),
              const SizedBox(height: 8),
              Text(message),
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
    );
  }
}

String _text(dynamic value) {
  if (value == null) return '';
  return value.toString();
}
