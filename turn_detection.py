"""Voice turn boundaries for hands-free Kesara conversations.

A small state machine separates waiting for speech, detecting user speech,
and detecting a natural pause. Timeouts are independent of model decoding.
"""

class TurnDetector:
    def __init__(self, silence_seconds=1.05, min_speech_seconds=0.22,
                 max_wait_seconds=15.0, max_turn_seconds=35.0):
        self.silence_seconds=silence_seconds
        self.min_speech_seconds=min_speech_seconds
        self.max_wait_seconds=max_wait_seconds
        self.max_turn_seconds=max_turn_seconds
        self.started=False
        self.first_speech=None
        self.last_speech=None
        self.reason=None

    def update(self, seconds, speech_end=None):
        """Update from VAD: speech_end is last detected speech time in recording.

        Returns 'speech_started', 'speech_finished', 'waiting_timeout',
        'turn_timeout', or None.
        """
        if speech_end is not None:
            if not self.started:
                self.first_speech=speech_end
                self.started=True
                self.last_speech=speech_end
                return 'speech_started'
            self.last_speech=max(self.last_speech,speech_end)
        if self.started:
            if seconds>=self.max_turn_seconds:
                self.reason='turn_timeout'
                return self.reason
            if (self.last_speech is not None and
                    seconds-self.last_speech>=self.silence_seconds and
                    self.last_speech-self.first_speech>=self.min_speech_seconds):
                self.reason='speech_finished'
                return self.reason
        elif seconds>=self.max_wait_seconds:
            self.reason='waiting_timeout'
            return self.reason
        return None

def last_speech_end(data,rate):
    """Find the most recent voiced moment in the last 2 seconds of capture."""
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    waveform=np.frombuffer(data,dtype=np.int16).astype(np.float32)/32768.
    if rate!=16000:
        waveform=np.interp(np.arange(int(len(waveform)*16000/rate))*rate/16000,
                           np.arange(len(waveform)),waveform).astype(np.float32)
    if len(waveform)<6400:
        return None
    window=waveform[-32000:]
    parts=get_speech_timestamps(window,
        VadOptions(threshold=.38,min_speech_duration_ms=100,
                   min_silence_duration_ms=200,speech_pad_ms=0),sampling_rate=16000)
    if not parts:
        return None
    return (len(waveform)-len(window)+parts[-1]['end'])/16000.
