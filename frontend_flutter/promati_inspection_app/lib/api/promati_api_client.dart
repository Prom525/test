import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiStatus {
  final bool online;
  final String message;

  const ApiStatus({required this.online, required this.message});
}

class ValidationQueueResponse {
  final int count;
  final List<ValidationQueueItem> results;

  const ValidationQueueResponse({required this.count, required this.results});

  factory ValidationQueueResponse.fromJson(Map<String, dynamic> json) {
    final rawResults = json['results'];

    return ValidationQueueResponse(
      count: _asInt(json['count']) ?? 0,
      results: rawResults is List
          ? rawResults
                .whereType<Map<String, dynamic>>()
                .map(ValidationQueueItem.fromJson)
                .toList()
          : const [],
    );
  }
}

class ValidationQueueItem {
  final Map<String, dynamic> raw;

  const ValidationQueueItem(this.raw);

  factory ValidationQueueItem.fromJson(Map<String, dynamic> json) {
    return ValidationQueueItem(json);
  }

  String get submissionId =>
      _asString(raw['submission_id']) ??
      _asString(raw['id']) ??
      _asString(raw['client_submission_id']) ??
      '-';

  String get validationStatus =>
      _asString(raw['validation_status']) ?? 'ONBEKEND';

  String get userDisplay =>
      _asString(raw['user_name']) ?? _asString(raw['user_id']) ?? 'Onbekend';

  String get customerDisplay =>
      _asString(raw['customer_name']) ??
      _asString(raw['customer_id']) ??
      'Onbekende klant';

  String get siteDisplay =>
      _asString(raw['site_name']) ?? _asString(raw['site_id']) ?? '';

  String get submittedAt => _asString(raw['submitted_at']) ?? '';

  int get itemCount => _asInt(raw['item_count']) ?? 0;

  int get validationIssueCount => _asInt(raw['validation_issue_count']) ?? 0;

  bool get readyForPlannerApproval =>
      _asBool(raw['ready_for_planner_approval']) ?? false;
}

class PromatiApiClient {
  static const String defaultBaseUrl = String.fromEnvironment(
    'PROMATI_API_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  final String baseUrl;
  final http.Client _client;

  PromatiApiClient({String? baseUrl, http.Client? client})
    : baseUrl = baseUrl ?? defaultBaseUrl,
      _client = client ?? http.Client();

  Future<ApiStatus> checkHealth() async {
    try {
      final response = await _client
          .get(_uri('/healthz'))
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        return ApiStatus(
          online: true,
          message: 'API online: ${data['status']}',
        );
      }

      return ApiStatus(
        online: false,
        message: 'API fout: HTTP ${response.statusCode}',
      );
    } catch (e) {
      return ApiStatus(online: false, message: 'API niet bereikbaar: $e');
    }
  }

  Future<ValidationQueueResponse> getValidationQueue({int limit = 50}) async {
    final response = await _client
        .get(_uri('/validation/queue', {'limit': '$limit'}))
        .timeout(const Duration(seconds: 10));

    if (response.statusCode != 200) {
      throw Exception(
        'Validatiewachtrij kon niet geladen worden: HTTP ${response.statusCode}',
      );
    }

    final data = jsonDecode(response.body) as Map<String, dynamic>;
    return ValidationQueueResponse.fromJson(data);
  }

  Uri _uri(String path, [Map<String, String>? query]) {
    final cleanBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;

    return Uri.parse('$cleanBase$path').replace(queryParameters: query);
  }
}

String? _asString(dynamic value) {
  if (value == null) return null;
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

int? _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

bool? _asBool(dynamic value) {
  if (value is bool) return value;
  if (value is String) {
    final lower = value.toLowerCase();
    if (lower == 'true') return true;
    if (lower == 'false') return false;
  }
  return null;
}
