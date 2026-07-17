
import 'package:flutter/material.dart';

class PredictionResponse {
  final bool ok;
  final String? error;
  final String? inputUrl;
  final String? normalizedUrl;
  final PredictionResult? result;
  final String? model;
  final double? inferenceMs;

  PredictionResponse({
    required this.ok,
    this.error,
    this.inputUrl,
    this.normalizedUrl,
    this.result,
    this.model,
    this.inferenceMs,
  });

  factory PredictionResponse.fromJson(Map<String, dynamic> json) {
    return PredictionResponse(
      ok: json['ok'] ?? false,
      error: json['error'],
      inputUrl: json['input_url'],
      normalizedUrl: json['normalized_url'],
      result: json['result'] != null ? PredictionResult.fromJson(json['result']) : null,
      model: json['model'],
      inferenceMs: (json['inference_ms'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'ok': ok,
      'error': error,
      'input_url': inputUrl,
      'normalized_url': normalizedUrl,
      'result': result?.toJson(),
      'model': model,
      'inference_ms': inferenceMs,
    };
  }
}

class PredictionResult {
  final String badge;
  final String label;
  final String confidence;
  final double? phishingScore;
  final double? modelPhishingScore;
  final double? fusedPhishingScore;
  final double? threshold;
  final String riskLevel;
  final String? explanation;
  final String? ruleTrigger;
  final List<String>? recommendations;
  final ThreatIntelResult? threatIntel;
  final bool fusionApplied;

  PredictionResult({
    required this.badge,
    required this.label,
    required this.confidence,
    this.phishingScore,
    this.modelPhishingScore,
    this.fusedPhishingScore,
    this.threshold,
    required this.riskLevel,
    this.explanation,
    this.ruleTrigger,
    this.recommendations,
    this.threatIntel,
    this.fusionApplied = false,
  });

  factory PredictionResult.fromJson(Map<String, dynamic> json) {
    return PredictionResult(
      badge: json['badge'] ?? '',
      label: json['label'] ?? '',
      confidence: json['confidence'] ?? '',
      phishingScore: (json['phishing_score'] as num?)?.toDouble(),
      modelPhishingScore: (json['model_phishing_score'] as num?)?.toDouble(),
      fusedPhishingScore: (json['fused_phishing_score'] as num?)?.toDouble(),
      threshold: (json['threshold'] as num?)?.toDouble(),
      riskLevel: json['risk_level'] ?? '',
      explanation: json['explanation'],
      ruleTrigger: json['rule_trigger'],
      recommendations: List<String>.from(json['recommendations'] ?? []),
      threatIntel: json['threat_intel'] != null
          ? ThreatIntelResult.fromJson(
              Map<String, dynamic>.from(json['threat_intel']),
            )
          : null,
      fusionApplied: json['fusion_applied'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'badge': badge,
      'label': label,
      'confidence': confidence,
      'phishing_score': phishingScore,
      'model_phishing_score': modelPhishingScore,
      'fused_phishing_score': fusedPhishingScore,
      'threshold': threshold,
      'risk_level': riskLevel,
      'explanation': explanation,
      'rule_trigger': ruleTrigger,
      'recommendations': recommendations,
      'threat_intel': threatIntel?.toJson(),
      'fusion_applied': fusionApplied,
    };
  }

  bool get isPhishing => label.toLowerCase() == 'phishing';
  bool get isLegitimate => label.toLowerCase() == 'legitimate';
  bool get isUncertain => label.toLowerCase() == 'uncertain';

  Color get badgeColor {
    if (isPhishing) return const Color(0xFFFF6978);
    if (isUncertain) return const Color(0xFFFFD26F);
    return const Color(0xFF63F0A3);
  }

  Color get riskColor {
    final risk = riskLevel.toLowerCase();
    if (risk.contains('critical')) return const Color(0xFFFF6978);
    if (risk.contains('manual') || risk.contains('review')) {
      return const Color(0xFFFFD26F);
    }
    if (risk.contains('high')) return const Color(0xFFFF6978);
    if (risk.contains('medium')) return const Color(0xFFFFD26F);
    return const Color(0xFF63F0A3);
  }
}

class ThreatIntelResult {
  final bool checked;
  final String provider;
  final String verdict;
  final bool malicious;
  final double confidence;
  final String reason;
  final double latencyMs;
  final bool cacheHit;

  ThreatIntelResult({
    required this.checked,
    required this.provider,
    required this.verdict,
    required this.malicious,
    required this.confidence,
    required this.reason,
    required this.latencyMs,
    required this.cacheHit,
  });

  factory ThreatIntelResult.fromJson(Map<String, dynamic> json) {
    return ThreatIntelResult(
      checked: json['checked'] ?? false,
      provider: json['provider'] ?? '',
      verdict: json['verdict'] ?? 'unknown',
      malicious: json['malicious'] ?? false,
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      reason: json['reason'] ?? '',
      latencyMs: (json['latency_ms'] as num?)?.toDouble() ?? 0.0,
      cacheHit: json['cache_hit'] ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'checked': checked,
      'provider': provider,
      'verdict': verdict,
      'malicious': malicious,
      'confidence': confidence,
      'reason': reason,
      'latency_ms': latencyMs,
      'cache_hit': cacheHit,
    };
  }
}
