import 'package:flutter/material.dart';

import 'api/promati_api_client.dart';
import 'features/validation/validation_queue_page.dart';

void main() {
  runApp(const PromatiInspectionApp());
}

class PromatiInspectionApp extends StatelessWidget {
  const PromatiInspectionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'PROMATI Inspectie',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF1F4E79)),
        useMaterial3: true,
      ),
      home: const HomeScreen(),
    );
  }
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final PromatiApiClient api = PromatiApiClient();

  late Future<ApiStatus> apiStatus;

  @override
  void initState() {
    super.initState();
    apiStatus = api.checkHealth();
  }

  Future<void> refreshStatus() async {
    setState(() {
      apiStatus = api.checkHealth();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PROMATI Inspectieplatform'),
        actions: [
          IconButton(
            onPressed: refreshStatus,
            icon: const Icon(Icons.refresh),
            tooltip: 'API-status vernieuwen',
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            FutureBuilder<ApiStatus>(
              future: apiStatus,
              builder: (context, snapshot) {
                final status = snapshot.data;

                return Card(
                  child: ListTile(
                    leading: Icon(
                      status?.online == true
                          ? Icons.check_circle
                          : Icons.error_outline,
                      color: status?.online == true ? Colors.green : Colors.red,
                    ),
                    title: const Text('Backend API'),
                    subtitle: Text(
                      snapshot.connectionState == ConnectionState.waiting
                          ? 'Controleren...'
                          : status?.message ?? 'Onbekende status',
                    ),
                  ),
                );
              },
            ),
            const SizedBox(height: 24),
            _MenuCard(
              title: 'Monteur app',
              subtitle:
                  'Planning downloaden, offline inspecteren en synchroniseren.',
              icon: Icons.engineering,
              onTap: () => _showComingSoon(context, 'Monteur app'),
            ),
            _MenuCard(
              title: 'Planner',
              subtitle: 'Inspectieplannen maken, publiceren en opvolgen.',
              icon: Icons.calendar_month,
              onTap: () => _showComingSoon(context, 'Planner'),
            ),
            _MenuCard(
              title: 'Validatie',
              subtitle:
                  'Mobiele inspecties controleren, goedkeuren en promoveren.',
              icon: Icons.verified,
              onTap: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (_) => ValidationQueuePage(apiClient: api),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showComingSoon(BuildContext context, String module) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('$module wordt in de volgende stap gebouwd.')),
    );
  }
}

class _MenuCard extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  const _MenuCard({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: ListTile(
        leading: Icon(icon, size: 36),
        title: Text(title),
        subtitle: Text(subtitle),
        trailing: const Icon(Icons.chevron_right),
        onTap: onTap,
      ),
    );
  }
}
