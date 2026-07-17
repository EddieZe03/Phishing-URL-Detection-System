import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/prediction_model.dart';

class ApiService {
  static const String _apiBaseUrlFromEnv = String.fromEnvironment('API_BASE_URL');
  static String _runtimeBaseUrl = '';

  // Base URL priority:
  // 1) Runtime override via setBaseUrl(...)
  // 2) --dart-define=API_BASE_URL=http://...
  // 3) Platform default
  static String get baseUrl {
    if (_runtimeBaseUrl.isNotEmpty) return _runtimeBaseUrl;
    if (_apiBaseUrlFromEnv.isNotEmpty) return _normalizeBaseUrl(_apiBaseUrlFromEnv);
    return _defaultBaseUrl();
  }

  static String _defaultBaseUrl() {
    if (kIsWeb) return 'http://localhost:5000';

    // Android emulator uses 10.0.2.2 to reach host machine localhost.
    // For Android real device over USB, run: adb reverse tcp:5000 tcp:5000
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:5000';
    }

    // iOS simulator can use localhost directly.
    return 'http://localhost:5000';
  }

  static String _normalizeBaseUrl(String url) {
    final trimmed = url.trim();
    if (trimmed.endsWith('/')) {
      return trimmed.substring(0, trimmed.length - 1);
    }
    return trimmed;
  }

  static Future<PredictionResponse> predictUrl(String url, {String source = 'url'}) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/api/predict'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'url': url, 'source': source}),
      ).timeout(const Duration(seconds: 45));

      if (response.statusCode == 200) {
        return PredictionResponse.fromJson(jsonDecode(response.body));
      } else {
        return PredictionResponse(
          ok: false,
          error: 'Server error: ${response.statusCode}',
        );
      }
    } on TimeoutException {
      return PredictionResponse(
        ok: false,
        error: 'Request timed out. The backend may be offline or still warming up. Please try again in a few seconds.',
      );
    } catch (e) {
      return PredictionResponse(
        ok: false,
        error: 'Network error: $e',
      );
    }
  }

  static Future<bool> checkHealth() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/health'),
      ).timeout(const Duration(seconds: 20));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  static void setBaseUrl(String newUrl) {
    _runtimeBaseUrl = _normalizeBaseUrl(newUrl);
  }
}
