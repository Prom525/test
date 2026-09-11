class AppConfig {
  static const String _configuredApiBaseUrl = String.fromEnvironment(
    'PROMATI_API_BASE_URL',
    defaultValue: '',
  );

  static String get apiBaseUrl {
    final value = _configuredApiBaseUrl.trim();
    if (value.isEmpty) {
      throw StateError(
        'PROMATI_API_BASE_URL is niet ingesteld. '
        'Build/run met --dart-define=PROMATI_API_BASE_URL=https://...',
      );
    }
    return value.endsWith('/') ? value.substring(0, value.length - 1) : value;
  }
}