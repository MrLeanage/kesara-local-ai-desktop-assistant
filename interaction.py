"""Local microphone standby and opt-in camera controls. No media is saved."""
import json,queue,re,threading,time
from pathlib import Path
import voice

QUIET={'silent','be silent','be quiet','quiet','stop talking','stop working','go to sleep','silent for a while','be silent for a while','be quiet for a while','sleep for a while'}
def command(text):
    text=re.sub(r'[^a-z ]',' ',text.lower());text=' '.join(text.split())
    match=wake_match(text)
    if match:text=text[match.end():].strip()
    text=re.sub(r'^please | please$','',text).strip()
    if text in QUIET:return 'quiet'
    return None

def wake_match(text):
    return re.match(r'^\s*(?:(?:hey|hi|hello|okay)[,!. ]+)?(?:kesara|kaesara|kessara|kasara|kesera|kaysara|cesara|keshara|kae[ -]+sara|kay[ -]+sarah?|ke[ -]+sara|k[ -]+sarah?)\b[,!. ]*',text,re.I)

def wake(text):return bool(wake_match(text))

def wake_tail(text):
    match=wake_match(text)
    return text[match.end():].strip() if match else ''

class Ambient:
    def __init__(self,emit):
        self.emit=emit;self.closed=threading.Event();self.interrupt=threading.Event()
        self.mode=None;self.device=None;self.thread=None
    def configure(self,mode,device=None):
        if mode!=self.mode or device!=self.device:
            self.interrupt.set();self.mode=mode;self.device=device
        if mode and (not self.thread or not self.thread.is_alive()):
            self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def close(self):self.mode=None;self.closed.set();self.interrupt.set()
    def run(self):
        while not self.closed.is_set():
            mode=self.mode
            if not mode:self.closed.wait(.15);continue
            self.interrupt.clear()
            if mode!=self.mode or self.closed.is_set():continue
            try:
                if mode=='wake':
                    def emit(kind,value):
                        if self.interrupt.is_set() or self.mode!='wake':return
                        if kind=='processing_voice':self.emit('standby_phase','Checking your call...')
                        elif kind=='status':self.emit('standby_phase','Say Kesara')
                        elif kind=='dictation' and value:
                            matched=wake(value) and command(value)!='quiet'
                            voice.diagnostic('wake_checked',matched=matched,characters=len(value))
                            self.emit('standby_heard',value)
                            if matched:
                                self.emit('ambient_wake',wake_tail(value))
                                self.interrupt.set()
                            else:self.emit('standby_phase','Name missed · click to talk')
                    voice.record(self.interrupt,emit,self.device,auto_end=True,discard_on_stop=True)
                else:self.listen_quiet()
            except Exception as exc:
                self.mode=None;self.emit('ambient_error',str(exc))
    def listen_quiet(self):
        import vosk,sounddevice as sd
        vosk.SetLogLevel(-1)
        if not hasattr(self,'model'):self.model=vosk.Model(str(voice.BASE/'speech-model'/'vosk-model-small-en-us-0.15'))
        grammar=json.dumps(sorted(QUIET)+['[unk]'])
        info=sd.query_devices(self.device,'input');rate=int(info['default_samplerate'])
        recognizer=vosk.KaldiRecognizer(self.model,rate,grammar)
        audio=queue.Queue(maxsize=30)
        def callback(data,*args):
            try:audio.put_nowait(bytes(data))
            except queue.Full:pass
        with voice.CAPTURE_LOCK:
            if self.interrupt.is_set():return
            with sd.RawInputStream(samplerate=rate,device=self.device,channels=1,dtype='int16',blocksize=int(rate*.1),callback=callback):
                while not self.interrupt.is_set() and not self.closed.is_set():
                    try:data=audio.get(timeout=.2)
                    except queue.Empty:continue
                    if recognizer.AcceptWaveform(data):
                        text=json.loads(recognizer.Result()).get('text','')
                        if command(text)=='quiet':self.emit('ambient_quiet',None);return

class HoldGesture:
    def __init__(self):self.name=None;self.since=0;self.latched=False
    def update(self,name,now):
        if name!=self.name:self.name=name;self.since=now;self.latched=False
        if name and not self.latched and now-self.since>=1.2:
            self.latched=True;return name
        return None

def hand_gesture(points):
    if len(points)!=21:return None
    # Tip distance from wrist is invariant to image rotation and mirrored cameras.
    def distance(a,b):return ((points[a].x-points[b].x)**2+(points[a].y-points[b].y)**2)**.5
    extended=[distance(t,0)>distance(p,0)*1.17 for t,p in [(8,6),(12,10),(16,14),(20,18)]]
    if all(extended):return 'quiet'
    thumb=points[4].y<points[3].y<points[2].y and distance(4,0)>distance(3,0)*1.1
    if thumb and not any(extended):return 'wake'
    return None

class Camera:
    def __init__(self,emit):self.emit=emit;self.stop=threading.Event();self.thread=None
    def start(self):
        if self.thread and self.thread.is_alive():return
        self.stop.clear();self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def close(self):self.stop.set()
    def run(self):
        capture=None
        try:
            import cv2,mediapipe as mp
            options=mp.tasks.vision.HandLandmarkerOptions(base_options=mp.tasks.BaseOptions(model_asset_path=str(voice.BASE/'assets'/'hand_landmarker.task')),running_mode=mp.tasks.vision.RunningMode.VIDEO,num_hands=1,min_hand_detection_confidence=.65,min_hand_presence_confidence=.65)
            with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
                capture=cv2.VideoCapture(0,cv2.CAP_DSHOW)
                capture.set(cv2.CAP_PROP_FRAME_WIDTH,640);capture.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                if not capture.isOpened():raise RuntimeError('Camera could not open. Check Windows camera permissions and other camera apps.')
                self.emit('camera_state','on');hold=HoldGesture()
                while not self.stop.is_set():
                    ok,frame=capture.read()
                    if not ok:raise RuntimeError('Camera stopped providing frames.')
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    result=detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb),int(time.monotonic()*1000))
                    name=hand_gesture(result.hand_landmarks[0]) if result.hand_landmarks else None
                    action=hold.update(name,time.monotonic())
                    if action:self.emit('camera_gesture',action)
                    self.stop.wait(.12)
        except Exception as exc:self.emit('camera_error',str(exc))
        finally:
            if capture is not None:capture.release()
            self.emit('camera_state','off')
