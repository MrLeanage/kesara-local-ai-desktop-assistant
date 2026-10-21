"""Character-first home screen. The detailed workspace is behind More."""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from character import RigCharacter
from photo_character import PhotoCharacter
from robot_character import RobotCharacter as Character

BG='#10151f'
TEXT='#e8edf5'
MUTED='#9cacc1'
ACCENT='#65e1bb'

class CompanionHome:
    def __init__(self,app):
        self.app=app
        self.window=tk.Toplevel(app.root)
        self.window.title('Kesara')
        self.window.protocol('WM_DELETE_WINDOW',app.close)
        icon=Path(__file__).resolve().parent/'kesara.ico'
        if icon.is_file():
            try:self.window.iconbitmap(str(icon))
            except tk.TclError:pass
        width=340;height=min(500,app.root.winfo_screenheight()-100)
        self.window.overrideredirect(True)
        self.window.attributes('-topmost',True)
        self.window.configure(bg='#ff00ff')
        self.window.attributes('-transparentcolor','#ff00ff')
        self.window.geometry(f'{width}x{height}+{app.root.winfo_screenwidth()-width-20}+{max(0,app.root.winfo_screenheight()-height-70)}')
        self.state=tk.StringVar(value='Getting ready...')
        self.hint=tk.StringVar(value='')
        self.avatar=Character(self.window,width=340,height=410)
        self.avatar.configure(bg='#ff00ff')
        self.avatar.bind('<ButtonPress-1>',self.drag_start)
        self.avatar.bind('<B1-Motion>',self.drag_move)
        self.avatar.bind('<ButtonRelease-1>',self.drag_end)
        self.avatar.bind('<Button-3>',self.show_menu)
        self.talk=app.button(self.window,'Getting ready...',self.primary,accent=True)
        self.talk.configure(wraplength=260,justify='center')

        self.more=app.button(self.window,'More',self.show_menu)
        self.more.pack(side='bottom',pady=(0,6))
        self.talk.pack(side='bottom',pady=(2,3))
        self.avatar.pack(fill='both',expand=True)
        self.menu=tk.Menu(self.window,tearoff=False)
        app.root.protocol('WM_DELETE_WINDOW',app.root.withdraw)
        self.window.after(100,self.update)

    def switch_avatar(self):
        photo=getattr(self.avatar,'is_photo',False)
        self.avatar.destroy()
        factory=Character if photo else PhotoCharacter
        self.avatar=factory(self.window,width=340,height=410)
        self.avatar.configure(bg='#ff00ff')
        self.avatar.pack(fill='both',expand=True)
        self.avatar.bind('<ButtonPress-1>',self.drag_start)
        self.avatar.bind('<B1-Motion>',self.drag_move)
        self.avatar.bind('<ButtonRelease-1>',self.drag_end)
        self.avatar.bind('<Button-3>',self.show_menu)

    def drag_start(self,event):
        self.drag_origin=(event.x_root,event.y_root,self.window.winfo_x(),self.window.winfo_y())
        self.dragged=False

    def drag_move(self,event):
        sx,sy,wx,wy=self.drag_origin
        dx,dy=event.x_root-sx,event.y_root-sy
        if abs(dx)+abs(dy)>5:self.dragged=True
        if not self.dragged:return
        x=max(0,min(self.window.winfo_screenwidth()-self.window.winfo_width(),wx+dx))
        y=max(0,min(self.window.winfo_screenheight()-self.window.winfo_height(),wy+dy))
        self.window.geometry(f'+{x}+{y}')

    def drag_end(self,event):
        if not getattr(self,'dragged',False):self.primary()

    def show_menu(self,event=None):
        self.menu.delete(0,'end')
        self.menu.add_command(label='Open workspace',command=self.show_workspace)
        self.menu.add_command(label='End conversation' if self.app.conversation else 'Start conversation',command=self.primary)
        self.menu.add_command(label='Disable name activation' if self.app.hands_free else 'Enable name activation (microphone)',command=self.app.toggle_hands_free)
        self.menu.add_command(label='Disable camera gestures' if self.app.camera_enabled else 'Enable camera gestures',command=self.app.toggle_camera)
        self.menu.add_command(label='Last speech heard in standby',command=lambda:messagebox.showinfo('Standby speech',self.app.last_standby_heard or 'No standby speech recognized yet.',parent=self.window))
        self.menu.add_command(label='Be quiet / idle',command=self.app.quiet)
        self.menu.add_command(label='Use animated robot' if getattr(self.avatar,'is_photo',False) else 'Use photographic Kesara',command=self.switch_avatar)
        self.menu.add_separator()
        self.menu.add_command(label='Quit Kesara',command=self.app.close)
        x=event.x_root if event else self.more.winfo_rootx()
        y=event.y_root if event else self.more.winfo_rooty()+self.more.winfo_height()
        try:self.menu.tk_popup(x,y)
        finally:self.menu.grab_release()

    def show_workspace(self):
        self.app.root.deiconify();self.app.root.lift()

    def primary(self):
        app=self.app
        if app.busy:
            if app.conversation:app.end_conversation()
            app.stop();return
        if app.conversation:app.end_conversation()
        else:
            if app.speech_in_progress:
                app.speaker.stop();app.speech_id+=1;app.speech_in_progress=False
            app.toggle_conversation()

    def update(self):
        app=self.app
        if not app.alive:return
        self.avatar.viseme=app.viseme
        self.avatar.set_state(app.avatar.mode);self.avatar.set_level(app.avatar.level)
        ready=app.voice_ready and app.model_ready
        self.talk.configure(state='normal' if ready or app.busy or app.conversation else 'disabled')
        self.talk.configure(text='Stop' if app.busy else ('End conversation' if app.conversation else 'Start talking'))
        if app.pending:
            self.state.set('Your approval is needed')
            self.hint.set('Review the proposed action in the approval window.')
        elif app.speech_in_progress:
            self.state.set('Speaking')
            self.hint.set('I’ll listen again when the reply finishes.' if app.conversation else 'Ready for another conversation when you are.')
        elif app.busy:
            self.state.set('Stopping...' if app.cancelled.is_set() else 'Thinking')
            self.hint.set('Finishing the current operation safely.' if app.cancelled.is_set() else 'Working locally on your request.')
        elif app.listening:
            processing=app.mic_button.cget('text')=='Transcribing...'
            self.state.set('Understanding...' if processing else 'Listening')
            self.hint.set('Recognizing your words locally.' if processing else 'Speak naturally, then pause.')
        elif 'voice issue' in app.status.get().lower() or 'request failed' in app.status.get().lower():
            self.state.set('Needs attention')
            self.hint.set('Open More for details. Text chat is still available.')
        elif self.avatar.rig_error:
            self.state.set('Portrait fallback · More')
            self.hint.set('3D renderer unavailable; portrait remains usable.')
        elif not ready:
            self.state.set('Getting ready...')
            self.hint.set('Preparing the local AI and voice.')
        else:
            self.state.set('Ready')
            self.hint.set('Microphone off. Start talking when you’re ready.' if not app.conversation else 'Getting ready to listen again.')
            if not app.conversation and 'draft' in app.status.get().lower():self.hint.set('Open More to send or clear your current draft.')
        draft=bool(app.composer.get('1.0','end').strip())
        if draft and not app.conversation and not app.busy and not app.listening:
            self.state.set('Message waiting · More')
        label=self.state.get()
        if label=='Ready':label='Click to talk' if not app.conversation else 'Preparing to listen'
        if app.conversation and not app.busy and not app.listening and not app.speech_in_progress:label='Preparing to listen'
        if label=='Click to talk' and app.hands_free:label=app.standby_phase+' · Mic on'
        if app.hands_free and 'Mic on' not in label:label+=' · Mic on'
        if app.camera_enabled:label+=' · Camera '+('on' if app.camera_active else 'starting')
        self.talk.configure(text=label)
        self.window.after(100,self.update)
