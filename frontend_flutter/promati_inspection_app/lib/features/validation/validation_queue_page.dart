import 'package:flutter/material.dart';

import '../../api/promati_api_client.dart';
import 'validation_submission_detail_page.dart';

class ValidationQueuePage extends StatefulWidget {
  final PromatiApiClient apiClient;

  const ValidationQueuePage({super.key, required this.apiClient});

  @override
  State<ValidationQueuePage> createState() => _ValidationQueuePageState();
}

class _ValidationQueuePageState extends State<ValidationQueuePage> {
  late Future<ValidationQueueResponse> queueFuture;

  @override
  void initState() {
    super.initState();
    queueFuture = widget.apiClient.getValidationQueue();
  }

  void refresh() {
    setState(() {
      queueFuture = widget.apiClient.getValidationQueue();
    });
  }

  void openDetail(ValidationQueueItem item) {
    Navigator.of(context)
        .push(
          MaterialPageRoute(
            builder: (_) => ValidationSubmissionDetailPage(
              apiClient: widget.apiClient,
              submissionId: item.submissionId,
            ),
          ),
        )
        .then((_) => refresh());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Validatiewachtrij'),
        actions: [
          IconButton(
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Vernieuwen',
          ),
        ],
      ),
      body: FutureBuilder<ValidationQueueResponse>(
        future: queueFuture,
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

          final data = snapshot.data;
          final items = data?.results ?? [];

          if (items.isEmpty) {
            return const Center(
              child: Text('Geen mobiele submissions in de validatiewachtrij.'),
            );
          }

          return ListView.separated(
            padding: const EdgeInsets.all(16),
            itemCount: items.length,
            separatorBuilder: (_, index) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final item = items[index];

              return _ValidationQueueCard(
                item: item,
                onTap: () => openDetail(item),
              );
            },
          );
        },
      ),
    );
  }
}

class _ValidationQueueCard extends StatelessWidget {
  final ValidationQueueItem item;
  final VoidCallback onTap;

  const _ValidationQueueCard({required this.item, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final hasIssues = item.validationIssueCount > 0;

    return Card(
      child: ListTile(
        onTap: onTap,
        leading: Icon(
          hasIssues ? Icons.warning_amber : Icons.assignment_turned_in,
          color: hasIssues ? Colors.orange : Colors.green,
        ),
        title: Text('${item.customerDisplay} ${item.siteDisplay}'.trim()),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(
            'Monteur: ${item.userDisplay}\n'
            'Status: ${item.validationStatus}\n'
            'Items: ${item.itemCount} | Issues: ${item.validationIssueCount}\n'
            'Submission: ${item.submissionId}',
          ),
        ),
        trailing: item.readyForPlannerApproval
            ? const Chip(
                label: Text('Klaar'),
                avatar: Icon(Icons.check, size: 18),
              )
            : const Icon(Icons.chevron_right),
        isThreeLine: true,
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
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 600),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, size: 48, color: Colors.red),
                const SizedBox(height: 16),
                const Text(
                  'Validatiewachtrij kon niet geladen worden.',
                  style: TextStyle(fontWeight: FontWeight.bold),
                ),
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
      ),
    );
  }
}
