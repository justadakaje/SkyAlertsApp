import 'dart:convert';
import 'dart:js_interop';

@JS('window.fetch')
external JSPromise<_FetchResponse> _jsFetch(JSString url);

extension type _FetchResponse._(JSObject _) implements JSObject {
  external int get status;
  external JSPromise<JSString> text();
}

Future<Map<String, dynamic>> fetchJsonMap(
  Uri uri, {
  Duration timeout = const Duration(seconds: 6),
}) async {
  final resp = await _jsFetch(uri.toString().toJS).toDart.timeout(timeout);
  if (resp.status < 200 || resp.status >= 300) {
    throw StateError('HTTP ${resp.status} for $uri');
  }
  final body = (await resp.text().toDart.timeout(timeout)).toDart;
  final decoded = jsonDecode(body);
  if (decoded is Map<String, dynamic>) return decoded;
  if (decoded is Map) return Map<String, dynamic>.from(decoded);
  throw const FormatException('Expected JSON object');
}
