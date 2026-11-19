"""Offline, user-triggered dictation and Windows speech output."""
import base64
import array
import datetime
import json
import math
from pathlib import Path
import queue
import subprocess
import threading
import time
from speech_corrections import apply_corrections, parse_corrections

BASE=Path(__file__).resolve().parent
MODEL_PATH=BASE/'speech-model'/'whisper-small.en'
SETTINGS=BASE/'voice-settings.json'
_model=None
_lock=threading.Lock()
CAPTURE_LOCK=threading.Lock()

def diagnostic(kind,**values):
    # Device/level/error metadata only: no recording or recognized words.
    with (BASE/'voice-diagnostics.jsonl').open('a',encoding='utf-8') as file:
        file.write(json.dumps({'time':datetime.datetime.now().isoformat(),'kind':kind,**values})+'\n')

def audio_level(data):
    values=array.array('h',bytes(data))[::8]
    rms=math.sqrt(sum(v*v for v in values)/max(len(values),1))
    db=20*math.log10(max(rms,1)/32768)
    return max(0,min(100,int((db+60)*2))),rms

MODEL_REPOSITORY='Systran/faster-whisper-small.en'
REQUIRED_MODEL_FILES=('model.bin','config.json','tokenizer.json','vocabulary.txt')

MODEL_CHOICES={
    'small.en':('Systran/faster-whisper-small.en',BASE/'speech-model'/'whisper-small.en'),
    'medium.en':('Systran/faster-whisper-medium.en',BASE/'speech-model'/'whisper-medium.en'),
}
_loaded_model_key=None

def chosen_speech_engine():
    engine=voice_options().get('speech_engine','whisper')
    return engine if engine in ('whisper','parakeet') else 'whisper'

def chosen_speech_model():
    key=voice_options().get('speech_model','small.en')
    return key if key in MODEL_CHOICES else 'small.en'

def missing_model_files(model_key=None):
    key=model_key or chosen_speech_model()
    folder=MODEL_CHOICES[key][1]
    return [name for name in REQUIRED_MODEL_FILES if not (folder/name).is_file()]

def ensure_speech_model(on_status=None):
    """Install only the selected offline speech engine; no paid cloud API."""
    if chosen_speech_engine()=='parakeet':
        from parakeet_backend import ensure_model
        return ensure_model(on_status)
    key=chosen_speech_model()
    repository,folder=MODEL_CHOICES[key]
    missing=missing_model_files(key)
    if not missing:
        return False
    if on_status:
        on_status('Downloading '+key+' speech model for local use...')
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(repo_id=repository,local_dir=str(folder),
                          allow_patterns=list(REQUIRED_MODEL_FILES))
    except Exception as exc:
        raise RuntimeError('Unable to download '+key+' offline model: '+str(exc)) from exc
    missing=missing_model_files(key)
    if missing:
        raise RuntimeError('Incomplete speech model: '+', '.join(missing))
    if on_status:
        on_status('Speech model '+key+' downloaded. Loading recognition...')
    return True

def load_model():
    global _model,_loaded_model_key
    if chosen_speech_engine()=='parakeet':
        from parakeet_backend import load_recognizer
        return load_recognizer()
    key=chosen_speech_model()
    with _lock:
        if _model is None or _loaded_model_key!=key:
            from faster_whisper import WhisperModel
            missing=missing_model_files(key)
            if missing:
                raise RuntimeError('Offline Whisper model files are not ready: '+', '.join(missing))
            _model=WhisperModel(str(MODEL_CHOICES[key][1]),device='cpu',
                                compute_type='int8',cpu_threads=2,
                                num_workers=1,local_files_only=True)
            _loaded_model_key=key
    return _model

def microphones():
    import sounddevice as sd
    return [(i,d['name']) for i,d in enumerate(sd.query_devices()) if d['max_input_channels']>0]

def voice_options():
    try:
        data=json.loads(SETTINGS.read_text(encoding='utf-8'))
        return data if isinstance(data,dict) else {}
    except (OSError,ValueError):
        return {}

def recognition_names():
    values=voice_options().get('recognition_names',['Kesara'])
    if not isinstance(values,list):values=['Kesara']
    return [v.strip()[:60] for v in values[:30] if isinstance(v,str) and v.strip()]

def preferred_microphone(devices=None):
    """Resolve a saved device by name; PortAudio indices can change on reboot."""
    saved=voice_options().get('microphone_name')
    if not saved:
        return None
    devices=devices if devices is not None else microphones()
    for index,name in devices:
        if name==saved:
            return index
    return None

def recognition_options(settings=None, names=None):
    """Neutral prompt avoids biasing Whisper toward invented technical words."""
    settings=settings if settings is not None else voice_options()
    names=names if names is not None else recognition_names()
    beam=2 if settings.get('recognition_mode')=='balanced' else 5
    options=dict(language='en',beam_size=beam,temperature=0,
                 condition_on_previous_text=False,
                 vad_filter=True,
                 vad_parameters={'threshold':0.42,'min_silence_duration_ms':600},
                 hallucination_silence_threshold=2)
    # Only user-provided vocabulary as hints; do not prime complete sentences.
    if names:
        options['initial_prompt']='Proper names: '+', '.join(names)+'.'
    return options

def transcribe_audio(data,rate):
    import numpy as np
    waveform=np.frombuffer(data,dtype=np.int16).astype(np.float32)/32768.0
    if rate!=16000:
        waveform=np.interp(np.arange(int(len(waveform)*16000/rate))*rate/16000,np.arange(len(waveform)),waveform).astype(np.float32)
    if chosen_speech_engine()=='parakeet':
        from parakeet_backend import transcribe
        transcript=transcribe(waveform)
        return apply_corrections(transcript,parse_corrections(voice_options().get('speech_corrections','')))
    options=recognition_options()
    beam=options['beam_size']
    segments,_=load_model().transcribe(waveform,**options)
    segments=list(segments)
    if beam<5 and segments and min(segment.avg_logprob for segment in segments)<-1.0:
        options['beam_size']=5;segments=list(load_model().transcribe(waveform,**options)[0])
    # Whisper can hallucinate plausible phrases during noise or silence.
    # Filter low-confidence segments before routing any words to the agent.
    transcript=filter_transcript_segments(segments)
    return apply_corrections(transcript,parse_corrections(voice_options().get('speech_corrections','')))

def filter_transcript_segments(segments):
    """Return only credible recognized speech; never manufacture text."""
    accepted=[segment.text.strip() for segment in segments if
              segment.text.strip() and
              segment.avg_logprob >= -0.85 and
              segment.no_speech_prob < 0.65]
    return ' '.join(accepted).strip()

def contains_real_speech(data,rate):
    """Independent VAD gate; prevents silence from reaching Whisper/agent."""
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    waveform=np.frombuffer(data,dtype=np.int16).astype(np.float32)/32768.
    if rate!=16000:
        waveform=np.interp(np.arange(int(len(waveform)*16000/rate))*rate/16000,
                           np.arange(len(waveform)),waveform).astype(np.float32)
    if len(waveform)<int(0.65*16000):
        return False
    timestamps=get_speech_timestamps(
        waveform,VadOptions(threshold=.55,min_speech_duration_ms=350,
                            min_silence_duration_ms=500,speech_pad_ms=0),
        sampling_rate=16000)
    return sum(segment['end']-segment['start'] for segment in timestamps)>=int(.4*16000)

def speech_finished(data,rate,pause_seconds=1.8):
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps,VadOptions
    waveform=np.frombuffer(data,dtype=np.int16).astype(np.float32)/32768.0
    if rate!=16000:
        waveform=np.interp(np.arange(int(len(waveform)*16000/rate))*rate/16000,np.arange(len(waveform)),waveform).astype(np.float32)
    if len(waveform)<16000*2:return False
    parts=get_speech_timestamps(waveform,VadOptions(threshold=.35,min_speech_duration_ms=250,min_silence_duration_ms=round(pause_seconds*1000),speech_pad_ms=0),sampling_rate=16000)
    return bool(parts) and (len(waveform)-parts[-1]['end'])>=16000*pause_seconds

def record(stop, emit, device=None,auto_end=False,discard_on_stop=False):
    with CAPTURE_LOCK:
        if stop.is_set():return
        return _record(stop,emit,device,auto_end,discard_on_stop)

def _record(stop, emit, device=None,auto_end=False,discard_on_stop=False):
    import sounddevice as sd
    load_model()
    info=sd.query_devices(device,'input')
    # Capture at the microphone's native sample rate to avoid relying on
    # unstable driver-side sample rate conversion. Convert to 16 kHz for VAD/ASR.
    rate=int(info['default_samplerate'])
    if rate<=0:
        rate=16000
    sd.check_input_settings(device=device,channels=1,dtype='int16',samplerate=rate)
    audio=queue.Queue(maxsize=400)
    chunks=[]
    blocks=0
    peak_rms=0
    dropped=0
    captured_frames=0
    def callback(data,frames,time_info,status):
        nonlocal dropped,captured_frames,peak_rms
        captured_frames+=frames
        level,rms=audio_level(data)
        peak_rms=max(peak_rms,rms)
        emit('level',level)
        emit('recording_seconds',captured_frames/rate)
        try: audio.put_nowait(bytes(data))
        except queue.Full: dropped+=1
    with sd.RawInputStream(samplerate=rate,blocksize=max(1,int(rate/10)),device=device,dtype='int16',channels=1,callback=callback):
        diagnostic('recording_started',device=str(info['name']),sample_rate=rate)
        emit('status','Listening — speak naturally, then pause.' if auto_end else 'Listening — speak, then click Done.')
        start=time.monotonic()
        last_endpoint_check=0
        while not stop.is_set() and time.monotonic()-start<30:
            try: block=audio.get(timeout=0.2)
            except queue.Empty: continue
            blocks+=1
            chunks.append(block)
            if auto_end and time.monotonic()-last_endpoint_check>.2:
                last_endpoint_check=time.monotonic()
                if speech_finished(b''.join(chunks)[-int(rate*2*5):],rate):break
    while not audio.empty():
        chunks.append(audio.get_nowait())
    seconds=captured_frames/rate
    emit('level',0)
    if discard_on_stop and stop.is_set():return
    emit('processing_voice',None)
    text=''
    started=time.monotonic()
    if seconds>=0.65 and contains_real_speech(b''.join(chunks),rate):
        text=transcribe_audio(b''.join(chunks),rate)
    diagnostic('recording_finished',engine=chosen_speech_engine() if chosen_speech_engine()=='parakeet' else chosen_speech_model(),blocks=blocks,captured_seconds=round(seconds,2),peak_rms=round(peak_rms,1),dropped_blocks=dropped,recognized=bool(text),transcription_seconds=round(time.monotonic()-started,2))
    if not text:
        if seconds<2:
            emit('no_speech',f'Only {seconds:.1f} seconds of audio captured. Click Talk, wait for Listening, speak a full sentence, then click Done.')
        elif peak_rms<30:
            emit('no_speech','Almost no microphone signal was captured. Open Settings and choose the microphone you are speaking into.')
        else:
            emit('no_speech',f'Captured {seconds:.1f} seconds of audio, but no English words were recognized. Try a clear sentence closer to the selected microphone.')
    emit('dictation',text)

class LegacySpeaker:
    def __init__(self):
        self.process=None
        self.on_viseme=None
        self.lock=threading.Lock()

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process=None

    def speak(self,text,output_file=None):
        self.stop()
        # Data travels through standard input; it is never interpolated into shell code.
        code='$ErrorActionPreference="Stop"; [Console]::InputEncoding=[Text.Encoding]::UTF8; Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Rate = 0; '
        if output_file:
            encoded=base64.b64encode(str(output_file).encode('utf-8')).decode()
            code+="$p=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')); $s.SetOutputToWaveFile($p); "
        code+='$t=[Console]::In.ReadToEnd(); $s.Speak($t); $s.Dispose()'
        synchronized=callable(self.on_viseme) and not output_file
        if synchronized:
            source='using System; using System.Speech.Synthesis; public class KesaraSpeech { public static void Run() { using(var s=new SpeechSynthesizer()) { s.VisemeReached += (o,e) => { Console.WriteLine(e.Viseme.ToString()); Console.Out.Flush(); }; s.Speak(Console.In.ReadToEnd()); } } }'
            code='$ErrorActionPreference="Stop"; [Console]::InputEncoding=[Text.Encoding]::UTF8; Add-Type -ReferencedAssemblies System.Speech -TypeDefinition '+"'"+source+"'; [KesaraSpeech]::Run()"
        command=base64.b64encode(code.encode('utf-16le')).decode()
        with self.lock:
            process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',command],stdin=subprocess.PIPE,stdout=subprocess.PIPE if synchronized else subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            self.process=process
        if synchronized:
            try:
                process.stdin.write(text.encode('utf-8'));process.stdin.close()
                for line in process.stdout:
                    try:self.on_viseme(int(line.strip()))
                    except (ValueError,TypeError):pass
                error=process.stderr.read();process.wait()
            finally:
                if self.on_viseme:self.on_viseme(0)
        else:_,error=process.communicate(text.encode('utf-8'))
        with self.lock:
            was_stopped=self.process is not process
        if process.returncode != 0 and not was_stopped:
            raise RuntimeError('Windows speech output failed. Check the installed Windows voices and audio device.')


class Speaker(LegacySpeaker):
    """Keep Windows speech loaded; task text travels through a data-only pipe."""
    def __init__(self):
        super().__init__()
        self.start_lock=threading.Lock();self.ready=threading.Event();self.pending={};self.sequence=0;self.current=None;self.closed=False

    def _write(self,line):
        if self.process and self.process.poll() is None:
            self.process.stdin.write((line+'\n').encode('utf-8'));self.process.stdin.flush()

    def prepare(self):
        with self.start_lock:
            if self.closed:raise RuntimeError('Speech output is closed.')
            if self.process and self.process.poll() is None and self.ready.is_set():return
            source=(BASE/'speech_worker.cs').read_text(encoding='utf-8-sig')
            encoded_source=base64.b64encode(source.encode('utf-8')).decode()
            code='$ErrorActionPreference="Stop"; $source=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String(\''+encoded_source+'\')); Add-Type -ReferencedAssemblies System.Speech -TypeDefinition $source; [KesaraVoiceWorker]::Run()'
            encoded=base64.b64encode(code.encode('utf-16le')).decode()
            self.ready.clear()
            started=time.monotonic()
            process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-EncodedCommand',encoded],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
            self.process=process
            if self.closed:process.terminate();return
            threading.Thread(target=self._read,args=(process,),daemon=True).start()
            if not self.ready.wait(15):
                process.terminate();raise RuntimeError('Windows speech output did not become ready.')
            if process.poll() is not None:raise RuntimeError('Windows speech output failed to start.')
            diagnostic('speech_worker_ready',seconds=round(time.monotonic()-started,3))

    def _read(self,process):
        try:
            for raw in process.stdout:
                parts=raw.decode('utf-8',errors='replace').strip().split('|')
                if parts[0]=='R':self.ready.set();continue
                if len(parts)<3:continue
                with self.lock:
                    request=self.pending.get(parts[1]);current=self.current
                if parts[0]=='V' and current==parts[1] and self.on_viseme:
                    if request and not request['first']:
                        request['first']=True;diagnostic('speech_first_viseme',seconds=round(time.monotonic()-request['started'],3))
                    try:self.on_viseme(int(parts[2]))
                    except (ValueError,TypeError):pass
                elif parts[0]=='D' and request:
                    request['error']=parts[2]!='ok';request['done'].set()
        finally:
            if self.process is process:
                self.ready.set()
                with self.lock:
                    for request in self.pending.values():request['error']=True;request['done'].set()

    def stop(self):
        with self.lock:
            self.current=None
            try:self._write('X')
            except (OSError,ValueError):pass
            for request in self.pending.values():request['done'].set()
        if self.on_viseme:self.on_viseme(0)

    def speak(self,text,output_file=None):
        if output_file:return LegacySpeaker().speak(text,output_file)
        self.prepare();self.stop()
        with self.lock:
            self.sequence+=1;identifier=str(self.sequence);self.current=identifier
            request={'done':threading.Event(),'error':False,'started':time.monotonic(),'first':False};self.pending[identifier]=request
            self._write('S|'+identifier+'|'+base64.b64encode(text.encode('utf-8')).decode())
        try:
            if not request['done'].wait(300):raise RuntimeError('Windows speech output timed out.')
            if request['error'] and not self.closed:raise RuntimeError('Windows speech output failed.')
        finally:
            with self.lock:
                self.pending.pop(identifier,None)
                if self.current==identifier:self.current=None
            if self.on_viseme:self.on_viseme(0)

    def close(self):
        self.closed=True;self.stop()
        with self.lock:
            try:self._write('Q')
            except (OSError,ValueError):pass
            process=self.process
        if process and process.poll() is None:
            def finish():
                try:process.wait(3)
                except subprocess.TimeoutExpired:process.terminate()
            threading.Thread(target=finish,daemon=True).start()
