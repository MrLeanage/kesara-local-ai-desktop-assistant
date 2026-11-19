"""Floating voice waveform; avatar rendering is disabled by default."""
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from waveform import WaveIndicator

BG='#10151f'
PANEL='#171f2c'
TEXT='#e8edf5'
MUTED='#9cacc1'
ACCENT='#65e1bb'

class CompanionHome:
    def __init__(self, app):
        self.app=app
        self.window=tk.Toplevel(app.root)
        self.window.title('Kesara — Voice')
        self.window.protocol('WM_DELETE_WINDOW',app.close)
        self.window.configure(bg=BG)
        self.window.attributes('-topmost',True)
        self.window.geometry('330x242+70+70')
        self.window.resizable(True,False)
        self.avatar=WaveIndicator(self.window,width=300,height=98,bg=BG)
        self.avatar.pack(fill='x',padx=10,pady=(8,2))
        self.phase=tk.StringVar(value='Initializing voice recognition...')
        self.detail=tk.StringVar(value='You can open chat while setup runs.')
        tk.Label(self.window,textvariable=self.phase,bg=BG,fg=TEXT,font=('Segoe UI',10,'bold')).pack(pady=(0,2))
        tk.Label(self.window,textvariable=self.detail,bg=BG,fg=MUTED,font=('Segoe UI',8),wraplength=290).pack(pady=(0,5))
        self.talk=app.button(self.window,'Start talking',self.primary,accent=True)
        self.talk.pack(fill='x',padx=14,pady=3)
        self.more=app.button(self.window,'Open chat / options',self.show_menu)
        self.more.pack(fill='x',padx=14,pady=3)
        self.menu=tk.Menu(self.window,tearoff=False)
        self.window.after(100,self.update)

    def show_workspace(self):
        self.app.root.deiconify()
        self.app.root.lift()

    def show_menu(self,event=None):
        app=self.app
        self.menu.delete(0,'end')
        self.menu.add_command(label='Open chat workspace',command=self.show_workspace)
        self.menu.add_command(label='End conversation' if app.conversation else 'Start conversation',command=self.primary)
        self.menu.add_command(label='Disable name activation' if app.hands_free else 'Enable name activation',command=app.toggle_hands_free)
        self.menu.add_command(label='Disable camera gestures' if app.camera_enabled else 'Enable camera gestures',command=app.toggle_camera)
        self.menu.add_command(label='Be quiet / idle',command=app.quiet)
        self.menu.add_separator()
        self.menu.add_command(label='Quit Kesara',command=app.close)
        try:self.menu.tk_popup(self.more.winfo_rootx(),self.more.winfo_rooty()+self.more.winfo_height())
        finally:self.menu.grab_release()

    def primary(self):
        app=self.app
        if app.busy:
            if app.conversation:app.end_conversation()
            app.stop()
        elif app.conversation:app.end_conversation()
        else:
            if app.speech_in_progress:
                app.speaker.stop()
                app.speech_id+=1
                app.speech_in_progress=False
            app.toggle_conversation()

    def update(self):
        app=self.app
        if not app.alive:return
        self.avatar.set_state(app.avatar.mode)
        self.avatar.set_level(app.avatar.level)
        # The floating voice window must work without opening the chat workspace.
        # Whisper readiness is sufficient to begin; Ollama may load on first turn.
        ready=app.voice_ready
        self.talk.configure(state='normal' if ready or app.busy or app.conversation else 'disabled')
        self.talk.configure(text='Stop task' if app.busy else ('End voice chat' if app.conversation else 'Start voice chat'))
        if app.pending:
            phase='Approval needed'
            detail='Review the proposed code or command in the approval window.'
        elif app.listening:
            if app.mic_button.cget('text')=='Transcribing...':
                phase='Transcribing'
                detail='Speech ended. Recognizing locally...'
            elif getattr(app,'user_speaking',False):
                phase='Hearing you'
                detail='I detected your speech. Continue talking naturally.'
            else:
                phase='Listening for speech'
                detail='Start talking. Kesara detects your pause automatically.'
        elif app.speech_in_progress:
            phase='Speaking'
            detail='I will listen again after replying.'
        elif app.busy:
            phase='Thinking'
            detail='Preparing an answer or working on your request.'
        elif app.conversation:
            phase='Voice chat active'
            detail='Preparing to listen again.'
        elif ready:
            phase='Ready to talk'
            detail='Press Start voice chat once; keep this window open.'
        else:
            phase='Voice unavailable' if app.mic_button.cget('text')=='Voice unavailable' else 'Preparing voice'
            detail='Open chat to see setup details, or use text chat.'
        self.phase.set(phase)
        self.detail.set(detail)
        self.window.after(100,self.update)
