"""Small vector character: no GPU, downloaded art, or rendering service."""
import math
import tkinter as tk
from pathlib import Path

class Character(tk.Canvas):
    COLORS={'idle':'#65e1bb','listening':'#65e1bb','thinking':'#b9a5ff','speaking':'#8dc6ff','approval':'#f0c87b','error':'#f0a2a2'}

    def __init__(self,parent,width=180,height=156):
        super().__init__(parent,width=width,height=height,bg='#171f2c',highlightthickness=0)
        self.base_width=width
        self.base_height=height
        self.mode='idle'
        self.phase=0
        self.level=0
        self.running=True
        self.draw()
        self.after(80,self.animate)
        self.bind('<Destroy>',lambda event:setattr(self,'running',False))

    def set_state(self,mode):
        self.mode=mode if mode in self.COLORS else 'idle'

    def set_level(self,value):self.level=value

    def draw(self):
        self.delete('all')
        t=self.phase
        color=self.COLORS[self.mode]
        bob=math.sin(t*.07)*1.5
        skin='#d8a47c'
        dark='#243149'
        self.create_oval(18,18,162,163,fill='#1d2a3a',outline=color,width=1)
        self.create_oval(40,153,140,165,fill='#10151f',outline='')
        # Legs, jacket, neck, head and hair.
        self.create_line(76,134,73,157,fill='#354861',width=14,capstyle='round')
        self.create_line(102,134,106,157,fill='#354861',width=14,capstyle='round')
        self.create_line(63,159,80,159,fill='#87a1bb',width=7,capstyle='round')
        self.create_line(101,159,119,159,fill='#87a1bb',width=7,capstyle='round')
        self.create_polygon(64,87+bob,115,87+bob,121,135,58,135,fill=dark,outline='#4a6483',smooth=True)
        self.create_rectangle(82,76+bob,98,93+bob,fill=skin,outline='')
        self.create_line(90,94+bob,90,126,fill=color,width=2)
        self.create_oval(67,34+bob,113,84+bob,fill=skin,outline='#efc6a5',width=1)
        self.create_oval(66,29+bob,114,56+bob,fill='#263345',outline='')
        self.create_polygon(68,47+bob,74,34+bob,104,35+bob,113,48+bob,103,43+bob,92,47+bob,81,42+bob,fill='#263345',smooth=True)
        # Headset is a visible cue that this is an AI assistant character.
        self.create_arc(61,27+bob,119,85+bob,start=0,extent=180,outline=color,width=3,style='arc')
        self.create_rectangle(61,54+bob,68,68+bob,fill=color,outline='')
        self.create_rectangle(112,54+bob,119,68+bob,fill=color,outline='')
        self.create_line(116,67+bob,110,76+bob,102,76+bob,fill=color,width=2)
        # Blinking, looking toward the user, and thinking eyebrows.
        blink=(t%61 in (0,1))
        gaze=2 if self.mode=='thinking' else 0
        for x in (79,101):
            if blink:self.create_line(x-3,59+bob,x+3,59+bob,fill=dark,width=2)
            else:
                self.create_oval(x-3+gaze,56+bob,x+3+gaze,62+bob,fill=dark,outline='')
                self.create_oval(x-1+gaze,56+bob,x+gaze,58+bob,fill='white',outline='')
        tilt=2 if self.mode in ('thinking','approval') else 0
        self.create_line(75,51+bob+tilt,83,50+bob,fill=dark,width=2)
        self.create_line(97,50+bob,105,51+bob-tilt,fill=dark,width=2)
        if self.mode=='speaking':
            opening=2+abs(math.sin(t*.65))*6
            self.create_oval(84,70+bob-opening/2,97,70+bob+opening/2,fill='#623d43',outline='')
        elif self.mode in ('thinking','approval','error'):
            self.create_line(85,72+bob,96,72+bob,fill='#623d43',width=2)
        else:self.create_arc(82,63+bob,99,76+bob,start=200,extent=140,style='arc',outline='#623d43',width=2)
        # Articulated arms and hands; conversational gestures are state-driven.
        gesture=math.sin(t*.15)*5 if self.mode=='speaking' else 0
        if self.mode=='thinking':left=(55,105,73,78+bob)
        elif self.mode=='listening':left=(50,102,56,71+bob)
        else:left=(48,108,43,122+gesture)
        right=(129,105,144,88+gesture) if self.mode in ('speaking','approval') else (131,109,139,125)
        for shoulder,elbow_hand in ((66,left),(113,right)):
            ex,ey,hx,hy=elbow_hand
            self.create_line(shoulder,94+bob,ex,ey,hx,hy,fill='#415b78',width=10,capstyle='round',joinstyle='round')
            self.create_oval(hx-5,hy-5,hx+5,hy+5,fill=skin,outline='#efc6a5')
            self.create_line(hx,hy-2,hx+1,hy-7,fill=skin,width=3,capstyle='round')
        if self.mode=='listening':
            for i in range(3):
                height=3+((self.level/100)*15)*(0.5+abs(math.sin(t*.2+i)))
                x=146+i*6
                self.create_line(x,54-height,x,54+height,fill=color,width=3)
        if self.mode=='thinking':
            for i in range(3):
                x=133+i*9
                self.create_oval(x,39,x+4,43,fill=color if t//5%3==i else '#44546a',outline='')
        width=self.winfo_width() if self.winfo_width()>5 else self.base_width
        height=self.winfo_height() if self.winfo_height()>5 else self.base_height
        scale=min(width/180,height/176)
        self.scale('all',0,0,scale,scale)
        self.move('all',(width-180*scale)/2,(height-176*scale)/2)

    def animate(self):
        if not self.running:return
        self.phase+=1
        self.draw()
        self.after(80,self.animate)


VectorCharacter=Character

class RealisticCharacter(tk.Canvas):
    COLORS=VectorCharacter.COLORS
    def __init__(self,parent,width=180,height=156):
        from PIL import Image
        super().__init__(parent,width=width,height=height,bg='#171f2c',highlightthickness=0)
        self.mode='idle';self.phase=0;self.level=0;self.running=True
        self.base_width=width;self.base_height=height
        self.is_realistic=True
        path=Path(__file__).resolve().parent/'assets'/'kesara-realistic-sheet.png'
        floating=path.with_name('kesara-floating-sheet.png')
        if floating.is_file():path=floating
        with Image.open(path) as sheet:
            w,h=sheet.width//3,sheet.height//2
            self.frames=[sheet.crop((x*w,y*h,(x+1)*w,(y+1)*h)).convert('RGBA') for y in range(2) for x in range(3)]
        self.sized={};self.previous=None;self.current_index=None;self.transition=1
        self.image_item=self.create_image(0,0,anchor='center')
        self.bind('<Destroy>',lambda event:setattr(self,'running',False))
        self.draw();self.after(100,self.animate)

    def set_state(self,mode):self.mode=mode if mode in self.COLORS else 'idle'
    def set_level(self,value):self.level=value

    def draw(self):
        from PIL import Image,ImageOps,ImageTk
        width=self.winfo_width() if self.winfo_width()>5 else self.base_width
        height=self.winfo_height() if self.winfo_height()>5 else self.base_height
        size=(width,height)
        if size not in self.sized:
            self.sized={size:[ImageOps.fit(frame,size,method=Image.Resampling.LANCZOS,centering=(.5,.45)) for frame in self.frames]}
            self.previous=None;self.current_index=None
        frames=self.sized[size]
        if self.mode=='speaking':index=3 if self.phase//3%2==0 else 4
        elif self.mode=='listening':index=1
        elif self.mode in ('thinking','approval','error'):index=2
        else:index=5 if self.phase%100<12 else 0
        if index!=self.current_index:
            self.previous=frames[self.current_index] if self.current_index is not None else frames[index]
            self.current_index=index;self.transition=0
        self.transition=min(1,self.transition+.5)
        frame=Image.blend(self.previous,frames[index],self.transition)
        # Windows color-key transparency needs hard alpha edges at display time.
        if self.cget('bg')=='#ff00ff':frame.putalpha(frame.getchannel('A').point(lambda a:255 if a>=128 else 0))
        self.photo=ImageTk.PhotoImage(frame,master=self)
        self.itemconfigure(self.image_item,image=self.photo)
        self.coords(self.image_item,width/2,height/2+math.sin(self.phase*.08))

    def animate(self):
        if not self.running:return
        if self.winfo_ismapped():self.phase+=1;self.draw()
        self.after(100,self.animate)


if (Path(__file__).resolve().parent/'assets'/'kesara-realistic-sheet.png').is_file():
    try:
        import PIL
        Character=RealisticCharacter
    except ImportError:pass


class RigCharacter(RealisticCharacter):
    """Continuous skeletal animation with the portrait as loading/error fallback."""
    def __init__(self,parent,width=300,height=300):
        self.rig=None;self.rig_ready=False;self.rig_error=None;self.viseme=0
        super().__init__(parent,width,height)
        self.enable_rig()
        self.bind('<Destroy>',self.close_rig,add='+')

    def enable_rig(self):
        if self.rig:return
        from rig_renderer import RigRenderer
        self.rig=RigRenderer();self.rig_error=None

    def close_rig(self,event=None):
        if event is not None and event.widget is not self:return
        if self.rig:self.rig.close();self.rig=None
        self.rig_ready=False

    def toggle_rig(self):
        if self.rig:self.close_rig();self.draw()
        else:self.enable_rig()

    def animate(self):
        if not self.running:return
        if self.rig:
            import queue,io
            from PIL import Image,ImageTk
            self.rig.mode(self.mode,self.viseme)
            latest=None
            try:
                while True:
                    kind,value=self.rig.frames.get_nowait()
                    if kind=='frame':latest=value
                    elif kind=='error':self.rig_error=value
            except queue.Empty:pass
            if latest:
                frame=Image.open(io.BytesIO(latest)).convert('RGBA')
                if frame.getbbox():
                    size=(max(1,self.winfo_width()),max(1,self.winfo_height()))
                    frame=frame.resize(size,Image.Resampling.LANCZOS)
                    frame.putalpha(frame.getchannel('A').point(lambda a:255 if a>=128 else 0))
                    self.photo=ImageTk.PhotoImage(frame,master=self)
                    self.itemconfigure(self.image_item,image=self.photo);self.coords(self.image_item,size[0]/2,size[1]/2)
                    if not self.rig_ready:
                        from voice import diagnostic
                        diagnostic("avatar_ready",renderer="local_3d")
                    self.rig_ready=True
            if self.rig_error:
                from voice import diagnostic
                diagnostic('avatar_error',error=self.rig_error);self.close_rig()
        if not self.rig_ready and self.winfo_ismapped():self.phase+=1;self.draw()
        self.after(60,self.animate)


# Prefer the identity-preserving photographic portrait when its assets are ready.
if (Path(__file__).resolve().parent/'assets'/'kesara-photo-registration.json').is_file():
    from photo_character import PhotoCharacter
    Character=PhotoCharacter


if (Path(__file__).resolve().parent/'assets'/'robot-animations.json').is_file():
    from robot_character import RobotCharacter
    Character=RobotCharacter
