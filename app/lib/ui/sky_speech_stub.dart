import 'dart:ui';

/// Non-web stub for spoken teleprompter playback.
bool get isSpeechSupported => false;

/// Speaks [text] using platform TTS when supported.
void speakText(
  String text, {
  double pitch = 1.0,
  double rate = 1.0,
  VoidCallback? onEnd,
  VoidCallback? onError,
}) {}

/// Stops any active spoken playback.
void stopSpeech() {}
