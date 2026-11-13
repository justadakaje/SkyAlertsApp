import 'dart:convert';
import 'dart:io';

Future<Map<String, dynamic>> fetchJsonMap(
  Uri uri, {
  Duration timeout = const Duration(seconds: 6),
}) async {
  final client = HttpClient()..connectionTimeout = timeout;
  try {
    final req = await client.getUrl(uri).timeout(timeout);
    req.headers.set(HttpHeaders.acceptHeader, 'application/json');
    final resp = await req.close().timeout(timeout);
    if (resp.statusCode < 200 || resp.statusCode >= 300) {
      throw StateError('HTTP ${resp.statusCode} for $uri');
    }
    final body = await resp.transform(utf8.decoder).join().timeout(timeout);
    final decoded = jsonDecode(body);
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) return Map<String, dynamic>.from(decoded);
    throw const FormatException('Expected JSON object');
  } finally {
    client.close(force: true);
  }
}
