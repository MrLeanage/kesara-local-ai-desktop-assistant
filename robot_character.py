"""Play cached frames of authored 3D robot animations without a live 3D engine."""
import io,json,time,zipfile,functools
from pathlib import Path
from collections import OrderedDict
import tkinter as tk
from PIL import Image,ImageTk

ASSETS=Path(__file__).resolve().parent/'assets'
COLORS={'idle':'#65e1bb','listening':'#65e1bb','thinking':'#b9a5ff','speaking':'#8dc6ff','approval':'#f0c87b','error':'#f0a2a2'}

class RobotFrames:
    def __init__(self):
        self.metadata=json.loads((ASSETS/'robot-animations.json').read_text(encoding='utf-8'))
        self.clips={clip['name']:clip for clip in self.metadata['clips']}
        self.archive=zipfile.ZipFile(ASSETS/'robot-animations.zip')
    @functools.lru_cache(maxsize=128)
    def get(self,clip,index,opened=0):
        clip=clip if clip in self.clips else 'Idle';index=index%self.clips[clip]['count']
        return Image.open(io.BytesIO(self.archive.read(f'{clip}/{index:04d}-{int(bool(opened))}.png'))).convert('RGBA')
    def render(self,width,height,clip,index,opened=0):
        source=self.get(clip,index,opened)
        scale=min(width/source.width,height/source.height)
        size=(max(1,round(source.width*scale)),max(1,round(source.height*scale)))
        frame=source.resize(size,Image.Resampling.BILINEAR)
        result=Image.new('RGBA',(width,height));result.alpha_composite(frame,((width-size[0])//2,height-size[1]))
        return result

_SHARED=None
def shared_frames():
    global _SHARED
    if _SHARED is None:_SHARED=RobotFrames()
    return _SHARED

class RobotCharacter(tk.Canvas):
    COLORS=COLORS
    is_robot=True
    is_photo=False
    rig=None
    rig_error=None
    def __init__(self,parent,width=180,height=156):
        super().__init__(parent,width=width,height=height,bg='#171f2c',highlightthickness=0)
        self.base_width=width;self.base_height=height;self.mode='idle';self.level=0;self.viseme=0;self.running=True
        self.renderer=shared_frames();self.clips=self.renderer.clips
        self.clip='Idle';self.clip_started=time.monotonic();self.last_wave=-100;self.speaking_started=0;self.thumb_used=False;self.cache=OrderedDict();self.last_key=None
        self.image_item=self.create_image(0,0,anchor='nw')
        self.bind('<Destroy>',lambda event:setattr(self,'running',False))
        self.draw();self.after(42,self.animate)
        from voice import diagnostic
        diagnostic('avatar_ready',renderer='cached_skeletal_robot')
    def play(self,clip):self.clip=clip;self.clip_started=time.monotonic()
    def set_state(self,mode):
        mode=mode if mode in COLORS else 'idle'
        if mode==self.mode:return
        self.mode=mode;now=time.monotonic()
        if mode=='listening' and now-self.last_wave>45:self.play('Wave');self.last_wave=now
        elif mode=='speaking':
            self.play('Yes');self.speaking_started=now;self.thumb_used=False
        elif mode=='error':self.play('No')
    def set_level(self,value):self.level=value
    def draw(self):
        width=self.winfo_width() if self.winfo_width()>5 else self.base_width
        height=self.winfo_height() if self.winfo_height()>5 else self.base_height
        if self.mode=='speaking' and self.clip=='Idle' and not self.thumb_used and time.monotonic()-self.speaking_started>6:
            self.play('ThumbsUp');self.thumb_used=True
        elapsed=time.monotonic()-self.clip_started;info=self.clips[self.clip]
        if self.clip!='Idle' and elapsed>=info['duration']:
            self.play('Idle');elapsed=0;info=self.clips['Idle']
        index=int(elapsed*info['fps'])%info['count']
        opened=int(self.mode=='speaking' and self.viseme not in (0,21))
        key=(width,height,self.clip,index,opened,self.cget('bg'))
        if key==self.last_key:return
        if key not in self.cache:
            frame=self.renderer.render(width,height,self.clip,index,opened)
            if self.cget('bg')=='#ff00ff':frame.putalpha(frame.getchannel('A').point(lambda a:255 if a>=128 else 0))
            self.cache[key]=ImageTk.PhotoImage(frame,master=self)
            if len(self.cache)>96:self.cache.popitem(last=False)
        self.cache.move_to_end(key);self.photo=self.cache[key];self.last_key=key
        self.itemconfigure(self.image_item,image=self.photo)
    def animate(self):
        if not self.running:return
        start=time.monotonic()
        if self.winfo_ismapped():self.draw()
        self.after(max(1,int((1/24-(time.monotonic()-start))*1000)),self.animate)
