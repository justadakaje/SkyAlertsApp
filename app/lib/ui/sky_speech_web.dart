import 'dart:js_interop';
import 'dart:ui';

@JS('window.speechSynthesis')
external _SpeechSynthesis? get _speechSynthesis;

@JS()
extension type _SpeechSynthesis._(JSObject _) implements JSObject {
  external void speak(_SpeechSynthesisUtterance utterance);
  external void cancel();
}

@JS('SpeechSynthesisUtterance')
extension type _SpeechSynthesisUtterance._(JSObject _) implements JSObject {
  external factory _SpeechSynthesisUtterance(String text);
  external set rate(double value);
  external set pitch(double value);
  external set onend(JSFunction? value);
  external set onerror(JSFunction? value);
}

/// Whether the browser exposes `window.speechSynthesis`.
bool get isSpeechSupported => _speechSynthesis != null;

/// Speaks [text] via the browser Web Speech API, cancelling any prior utterance.
void speakText(
  String text, {
  double pitch = 1.0,
  double rate = 1.0,
  VoidCallback? onEnd,
  VoidCallback? onError,
}) {
  final synth = _speechSynthesis;
  if (synth == null) {
    onError?.call();
    return;
  }
  synth.cancel();
  final utterance = _SpeechSynthesisUtterance(text)
    ..rate = rate
    ..pitch = pitch;
  if (onEnd != null) {
    utterance.onend = onEnd.toJS;
  }
  if (onError != null) {
    utterance.onerror = onError.toJS;
  }
  synth.speak(utterance);
}

/// Cancels any active Web Speech API utterance.
void stopSpeech() {
  _speechSynthesis?.cancel();
}
