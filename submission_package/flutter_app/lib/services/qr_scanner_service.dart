
class QrScannerService {
  static Future<String?> scanQr() async {
    // This will be called from the QR scan screen
    // mobile_scanner package handles the camera access
    return null;
  }

  static bool isValidUrl(String text) {
    return isProbableUrl(text);
  }

  static bool isProbableUrl(String text) {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return false;

    final lowered = trimmed.toLowerCase();
    if (lowered.startsWith('http://') || lowered.startsWith('https://')) {
      try {
        return Uri.parse(trimmed).host.isNotEmpty;
      } catch (e) {
        return false;
      }
    }

    if (trimmed.startsWith('www.')) {
      return trimmed.contains('.') && !trimmed.contains(RegExp(r'\s'));
    }

    if (trimmed.contains(RegExp(r'\s'))) {
      return false;
    }

    final hostCandidate = trimmed.split('/').first.split('?').first;
    return hostCandidate.contains('.') && RegExp(r'[A-Za-z]').hasMatch(hostCandidate);
  }

  static String normalizeUrl(String text) {
    final trimmed = text.trim();
    if (!trimmed.startsWith('http://') && !trimmed.startsWith('https://')) {
      return 'http://$trimmed';
    }
    return trimmed;
  }
}
