"""A hidden WebGL rig renderer; only its rendered frames reach the Tk desktop."""
import base64,functools,http.server,multiprocessing,queue,threading,time
from pathlib import Path

def render_worker(frames,states,stop,page="index.html"):
    frames.cancel_join_thread()
    import os
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"]="--disable-background-timer-throttling --disable-renderer-backgrounding --disable-backgrounding-occluded-windows"
    import webview
    class Static(http.server.SimpleHTTPRequestHandler):
        extensions_map={**http.server.SimpleHTTPRequestHandler.extensions_map,".mjs":"text/javascript",".js":"text/javascript"}
        def log_message(self,*args):pass
        def end_headers(self):
            self.send_header('Access-Control-Allow-Origin','null')
            super().end_headers()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Static,directory=str(Path(__file__).parent/'assets'/'three')))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    class Bridge:
        current={'mode':'idle'}
        def state(self):
            try:
                while True:self.current=states.get_nowait()
            except queue.Empty:pass
            return self.current
        def ready(self,info):frames.put(('ready',info))
        def error(self,error):
            try:frames.put_nowait(('error',error))
            except queue.Full:pass
        def frame(self,data,meta=None):
            if meta is not None:
                frames.put(('bake_frame',(meta,base64.b64decode(data.split(',',1)[1]))))
                return self.state()
            try:frames.put_nowait(('frame',base64.b64decode(data.split(',',1)[1])))
            except queue.Full:pass
            return self.state()
    window=webview.create_window('Kesara render engine',f'http://127.0.0.1:{server.server_port}/{page}',js_api=Bridge(),width=300,height=300,hidden=True,x=-1000,y=-1000,frameless=True,focus=False)
    def watch():
        stop.wait();window.destroy();server.shutdown()
    try:webview.start(watch,gui='edgechromium')
    except Exception as exc:
        try:frames.put_nowait(('error',str(exc)))
        except queue.Full:pass

class RigRenderer:
    def __init__(self):
        context=multiprocessing.get_context('spawn')
        self.frames=context.Queue(2);self.states=context.Queue(2);self.stop=context.Event()
        self.process=context.Process(target=render_worker,args=(self.frames,self.states,self.stop),daemon=True)
        self.process.start();self.last_mode=None
    def mode(self,value,viseme=0):
        state={'mode':value,'viseme':viseme}
        if state==self.last_mode:return
        try:self.states.put_nowait(state);self.last_mode=state
        except queue.Full:pass
    def close(self):
        self.stop.set()
        def finish():
            self.process.join(4)
            if self.process.is_alive():self.process.terminate();self.process.join(2)
        threading.Thread(target=finish,daemon=True).start()
