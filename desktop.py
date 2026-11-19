"""Kesara's local desktop chat and voice interface."""
import json
import re
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

import kesara as core
from waveform import WaveIndicator
from history import ChatHistory
from speech_corrections import parse_corrections, format_corrections
from voice_safety import requires_voice_review
from approval_policy import ApprovalPolicy
from interaction import Ambient, Camera, command as voice_command
from voice import Speaker, microphones, preferred_microphone, record, load_model, ensure_speech_model, diagnostic, recognition_names, SETTINGS as VOICE_SETTINGS

BG='#10151f'
PANEL='#171f2c'
CARD='#202b3b'
TEXT='#e8edf5'
MUTED='#9cacc1'
ACCENT='#65e1bb'

class App:
    def __init__(self,root):
        self.root=root
        self.events=queue.Queue()
        self.messages=[]
        self.history=ChatHistory(core.BASE/'chat-history.sqlite3')
        self.approval_policy=ApprovalPolicy(core.BASE/'approval-policy.json')
        previous=self.history.list_conversations()
        self.conversation_id=previous[0][0] if previous else self.history.create(core.PROJECTS.resolve())
        self.loading_chat=False
        self.streaming_reply=False
        self.model_ready=False
        self.model_error=None
        self.conversation=False
        self.pending_voice_send=False
        self.review_voice_pending=False
        self.last_voice_transcript=''
        self.last_voice_transcript_at=0.0
        self.last_spoken_reply=''
        self.speech_in_progress=False
        self.voice_reply_full=None
        self.voice_reply_visible=''
        self.voice_reply_target=''
        self.voice_reply_tick_active=False
        self.voice_playback_started=False
        self.speech_id=0
        self.speech_stream_queue=None
        self.speech_stream_cursor=0
        self.companion=None
        self.home=None
        self.standby_phase="Say Kesara"
        self.last_standby_heard=""
        self.hands_free=False
        self.camera_enabled=False
        self.camera_active=False
        self.ambient=Ambient(self.emit)
        self.camera=Camera(self.emit)
        self.root.after(250,self.interaction_tick)
        self.cwd=core.PROJECTS.resolve()
        self.cancelled=threading.Event()
        self.mic_stop=threading.Event()
        self.speaker=Speaker()
        self.viseme=0
        self.speaker.on_viseme=lambda value:self.emit('viseme',value)
        self.busy=False
        self.listening=False
        self.user_speaking=False
        self.voice_ready=False
        self.recording_seconds=0
        try:self.device=preferred_microphone()
        except Exception:self.device=None  # Missing/broken audio device must not block text chat.
        self.pending=None
        self.approval_window=None
        self.alive=True
        root.title('Kesara — Local AI Assistant')
        width=min(1120,root.winfo_screenwidth()-60)
        height=min(780,root.winfo_screenheight()-100)
        root.geometry(f'{width}x{height}+20+20')
        root.minsize(820,500)
        root.configure(bg=BG)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.option_add('*Font',('Segoe UI',10))

        sidebar=tk.Frame(root,bg=PANEL,width=230,padx=22,pady=16)
        sidebar.pack(side='left',fill='y')
        sidebar.pack_propagate(False)
        tk.Label(sidebar,text='KESARA',bg=PANEL,fg=TEXT,font=('Segoe UI',18,'bold')).pack(anchor='center')
        self.avatar=WaveIndicator(sidebar,width=180,height=85,bg=PANEL)
        self.avatar.pack(anchor='center')
        self.avatar.bind('<Button-1>',lambda event:self.open_companion())
        tk.Label(sidebar,text='Voice activity · click to expand',bg=PANEL,fg=MUTED,font=('Segoe UI',8)).pack(anchor='center',pady=(0,12))
        self.new_button=self.button(sidebar,'+  New conversation',self.new_chat)
        self.new_button.pack(fill='x',pady=5)
        tk.Label(sidebar,text='HISTORY',bg=PANEL,fg=MUTED,font=('Segoe UI',8,'bold')).pack(anchor='w',pady=(10,4))
        self.history_list=tk.Listbox(sidebar,bg=CARD,fg=TEXT,selectbackground='#344f65',relief='flat',borderwidth=0,height=9,font=('Segoe UI',9),exportselection=False)
        self.history_list.pack(fill='x',pady=(0,8))
        self.history_list.bind('<<ListboxSelect>>',self.open_history)
        self.history_rows=[]
        self.folder_button=self.button(sidebar,'Choose project folder',self.choose_folder)
        self.folder_button.pack(fill='x',pady=5)
        self.button(sidebar,'Settings',self.settings).pack(fill='x',pady=5)
        tk.Label(sidebar,text='WORKING FOLDER',bg=PANEL,fg=MUTED,font=('Segoe UI',8,'bold')).pack(anchor='w',pady=(12,6))
        self.folder_text=tk.StringVar(value=str(self.cwd))
        tk.Label(sidebar,textvariable=self.folder_text,bg=PANEL,fg=TEXT,wraplength=185,justify='left',font=('Segoe UI',9)).pack(anchor='w')
        bottom=tk.Frame(sidebar,bg=PANEL)
        bottom.pack(side='bottom',fill='x')
        tk.Label(bottom,text='●  LOCAL INFERENCE',bg=PANEL,fg=ACCENT,font=('Segoe UI',9,'bold')).pack(anchor='w')
        self.model_state=tk.StringVar(value='Qwen2.5-Coder · 3B\nPreparing local AI...')
        tk.Label(bottom,textvariable=self.model_state,bg=PANEL,fg=MUTED,justify='left',font=('Segoe UI',9)).pack(anchor='w',pady=(7,0))

        main=tk.Frame(root,bg=BG,padx=26,pady=24)
        main.pack(side='left',fill='both',expand=True)
        header=tk.Frame(main,bg=BG)
        header.pack(fill='x')
        tk.Label(header,text='Let’s build something.',bg=BG,fg=TEXT,font=('Segoe UI',19,'bold')).pack(side='left')
        self.conversation_button=self.button(header,'Start conversation',self.toggle_conversation,accent=True)
        self.conversation_button.pack(side='right')
        self.speak_enabled=tk.BooleanVar(value=True)
        policy_bar=tk.Frame(main,bg=BG)
        policy_bar.pack(fill='x',pady=(8,8))
        tk.Label(policy_bar,text='Tool permissions:',bg=BG,fg=MUTED).pack(side='left')
        self.policy_labels={
            'ask':'Ask before each action',
            'session_write':'Allow project writes this session',
            'session_all':'Allow writes + PowerShell this session',
            'always_write':'Always allow project writes',
            'always_all':'Always allow writes + PowerShell'
        }
        self.policy_choice=tk.StringVar(value=self.policy_labels[self.approval_policy.mode(self.cwd)])
        self.policy_picker=ttk.Combobox(policy_bar,values=list(self.policy_labels.values()),
                                        textvariable=self.policy_choice,state='readonly',width=40)
        self.policy_picker.pack(side='left',padx=8)
        self.policy_picker.bind('<<ComboboxSelected>>',self.change_permission_policy)
        self.button(policy_bar,'Reset',self.reset_permission_policy).pack(side='left')
        tk.Label(main,text='Permissions apply to the selected project. Spoken file commands still need transcript confirmation.',
                 bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(0,9))
        tk.Label(main,text='Code, prepare projects, and work with your files.',bg=BG,fg=MUTED).pack(anchor='w',pady=(0,9))

        # Reserve the composer and voice controls before allocating the chat pane.
        controls=tk.Frame(main,bg=BG)
        controls.pack(side='bottom',fill='x')
        self.chat=scrolledtext.ScrolledText(main,bg=PANEL,fg=TEXT,insertbackground=TEXT,relief='flat',padx=18,pady=16,wrap='word',font=('Segoe UI',11),state='disabled',height=8)
        self.chat.pack(fill='both',expand=True)
        for tag,color in [('you',ACCENT),('kesara','#a9baff'),('tool',MUTED),('system','#e6be79')]:
            self.chat.tag_configure(tag,foreground=color)
        self.chat.tag_configure('label',font=('Segoe UI',9,'bold'),spacing1=14,spacing3=5)
        self.load_conversation(self.conversation_id)

        self.status=tk.StringVar(value='Ready · All model and voice processing stays on this PC')
        tk.Label(controls,textvariable=self.status,bg=BG,fg=MUTED,anchor='w',wraplength=740,justify='left',font=('Segoe UI',9)).pack(fill='x',pady=(12,8))
        self.composer=tk.Text(controls,height=3,bg=CARD,fg=TEXT,insertbackground=ACCENT,relief='flat',padx=12,pady=10,wrap='word',font=('Segoe UI',11))
        self.composer.pack(fill='x')
        self.composer.bind('<Control-Return>',lambda event:self.send())
        bar=tk.Frame(controls,bg=BG)
        bar.pack(fill='x',pady=(10,0))
        self.mic_button=self.button(bar,'Loading voice...',self.toggle_mic)
        self.mic_button.pack(side='left')
        self.mic_button.configure(state='disabled')
        self.level=ttk.Progressbar(bar,length=65,maximum=100)
        self.level.pack(side='left',padx=(8,0))
        self.send_button=self.button(bar,'Send  →',self.primary_action,accent=True)
        self.send_button.pack(side='right')
        tk.Label(controls,text='Ctrl+Enter to send  ·  Voice input: English  ·  Commands run with your Windows permissions',bg=BG,fg=MUTED,font=('Segoe UI',8)).pack(anchor='w',pady=(10,0))
        root.after(60,self.poll)
        def prepare_voice():
            try:
                ensure_speech_model(on_status=lambda message:self.emit('voice_setup_status',message))
                self.emit('voice_setup_status','Loading local speech recognition...')
                load_model()
                self.emit('voice_ready',None)
            except Exception as exc:
                diagnostic('initialization_error',error=str(exc))
                self.emit('voice_error','Speech recognition could not load: '+str(exc))
                self.emit('voice_unavailable',None)
        threading.Thread(target=prepare_voice,daemon=True).start()
        def prepare_speech():
            try:self.speaker.prepare()
            except Exception as exc:diagnostic('speech_warm_error',error=str(exc))
        threading.Thread(target=prepare_speech,daemon=True).start()
        def prepare_model():
            try: core.warm_model(self.cwd);self.emit('model_ready',None)
            except Exception as exc:self.emit('model_warm_error',str(exc))
        threading.Thread(target=prepare_model,daemon=True).start()
        self.composer.focus_set()

    def refresh_permission_policy(self):
        if hasattr(self,'policy_choice'):
            self.policy_choice.set(self.policy_labels[self.approval_policy.mode(self.cwd)])

    def reset_permission_policy(self):
        self.approval_policy.set_mode(self.cwd,'ask')
        self.refresh_permission_policy()
        self.status.set('Tool permissions reset: ask before each action.')

    def change_permission_policy(self,event=None):
        choice=self.policy_choice.get()
        mode=next((key for key,label in self.policy_labels.items() if label==choice),'ask')
        if mode=='always_all':
            allowed=messagebox.askyesno('Persistent PowerShell access',
                'This grants Kesara persistent permission to WRITE files in this project AND RUN arbitrary PowerShell commands without asking again.\\n\\n'
                'PowerShell is not sandboxed and may access files outside the project. '
                'Only enable for a trusted project and trusted instructions. Continue?',
                parent=self.root)
            if not allowed:
                self.refresh_permission_policy();return
        elif mode=='session_all':
            allowed=messagebox.askyesno('Session PowerShell access',
                'For this running Kesara session, commands may execute without further approval. '
                'PowerShell is not restricted to the project directory. Continue?',parent=self.root)
            if not allowed:
                self.refresh_permission_policy();return
        self.approval_policy.set_mode(self.cwd,mode)
        self.status.set('Tool permissions for this project: '+self.policy_labels[mode])

    def button(self,parent,text,command,accent=False):
        return tk.Button(parent,text=text,command=command,bg=ACCENT if accent else CARD,fg=BG if accent else TEXT,activebackground='#8af0cf' if accent else '#304159',activeforeground=BG if accent else TEXT,relief='flat',borderwidth=0,padx=13,pady=9,cursor='hand2',font=('Segoe UI',10,'bold' if accent else 'normal'))

    def append(self,name,text,tag):
        if not self.loading_chat and name in ('You','Kesara','Tool result','Could not complete request','Conversation mode','Workspace'):
            self.history.add(self.conversation_id,name.lower(),text)
            self.refresh_history()
        self.chat.configure(state='normal')
        self.chat.insert('end',name.upper()+'\n',('label',tag))
        self.chat.insert('end',text+'\n\n',tag)
        self.chat.configure(state='disabled')
        self.chat.see('end')

    def refresh_history(self):
        self.history_rows=self.history.list_conversations()
        self.history_list.delete(0,'end')
        for _,title,_ in self.history_rows:
            self.history_list.insert('end',title)
        for i,(cid,_,_) in enumerate(self.history_rows):
            if cid==self.conversation_id:
                self.history_list.selection_set(i)
                break

    def load_conversation(self,conversation_id):
        self.loading_chat=True
        try:
            self.conversation_id=conversation_id
            self.messages=[]  # Display history is not executable tool state.
            self.chat.configure(state='normal')
            self.chat.delete('1.0','end')
            self.chat.configure(state='disabled')
            messages=self.history.messages(conversation_id)
            if not messages:
                self.append('Kesara','What would you like to build? Select a project and ask me to inspect its code. Changes and commands require approval.','kesara')
            else:
                for role,body in messages:
                    tag={'you':'you','kesara':'kesara','tool result':'tool'}.get(role,'system')
                    self.append(role.capitalize(),body,tag)
            project=self.history.project(conversation_id)
            if project and Path(project).is_dir():
                self.cwd=Path(project).resolve()
                self.folder_text.set(str(self.cwd))
                self.refresh_permission_policy()
            self.refresh_history()
        finally:
            self.loading_chat=False

    def open_history(self,event=None):
        if self.busy or self.listening or self.conversation:
            return
        selection=self.history_list.curselection()
        if selection:
            cid=self.history_rows[selection[0]][0]
            if cid!=self.conversation_id:
                self.load_conversation(cid)
    def emit(self,kind,value): self.events.put((kind,value))

    def expression(self,mode):
        self.avatar.set_state(mode)
        if self.companion and self.companion.winfo_exists():self.companion.set_state(mode)

    def open_companion(self):
        if self.companion and self.companion.winfo_exists():
            self.companion.winfo_toplevel().lift();return
        window=tk.Toplevel(self.root);window.title('Kesara — Voice');window.geometry('380x200');window.configure(bg=PANEL)
        self.companion=WaveIndicator(window,width=360,height=130,bg=PANEL)
        self.companion.pack(fill='both',expand=True,padx=10,pady=10)
        self.companion.set_state(self.avatar.mode)
        tk.Label(window,text='Kesara · Local voice activity',bg=PANEL,fg=MUTED).pack(pady=(0,14))

    def interaction_tick(self):
        if not self.alive:return
        mode=None
        if self.hands_free and self.voice_ready and not self.listening:
            mode='quiet' if self.busy or self.speech_in_progress else ('wake' if not self.conversation else None)
        self.ambient.configure(mode,self.device)
        if self.camera_enabled and (not self.camera.thread or not self.camera.thread.is_alive()):self.camera.start()
        state={'voice_ready':self.voice_ready,'model_ready':self.model_ready,'name_activation':self.hands_free,'conversation':self.conversation,'recording':self.listening,'busy':self.busy,'speaking':self.speech_in_progress,'camera_on':self.camera_active,'standby_phase':self.standby_phase,'draft_characters':len(self.composer.get('1.0','end').strip())}
        if state!=getattr(self,'last_runtime_state',None):
            self.last_runtime_state=state
            target=core.BASE/'runtime-state.json'
            temp=target.with_suffix('.tmp');temp.write_text(json.dumps(state),encoding='utf-8');temp.replace(target)
        self.root.after(250,self.interaction_tick)

    def toggle_hands_free(self):
        self.hands_free=not self.hands_free
        if not self.hands_free:self.ambient.configure(None)
        self.status.set('Wake listening on. Say Kesara, pause, then speak when Listening appears.' if self.hands_free else 'Wake listening off.')

    def toggle_camera(self):
        self.camera_enabled=not self.camera_enabled
        if self.camera_enabled:self.camera.start()
        else:self.camera.close()

    def quiet(self):
        self.ambient.configure(None)
        self.end_conversation();self.stop()
        self.status.set('Idle. Say Kesara to wake me.' if self.hands_free else 'Idle. Click to talk.')

    def preserve_draft(self):
        text=self.composer.get('1.0','end').strip()
        if not text:return
        self.append('Unsent draft (not submitted)',text,'system')
        with (core.BASE/'unsent-drafts.jsonl').open('a',encoding='utf-8') as file:
            file.write(json.dumps({'text':text})+'\n')
        self.composer.delete('1.0','end')

    def wake_up(self,text=None):
        if self.pending or self.busy or self.listening or self.speech_in_progress:return
        if not self.conversation:
            self.preserve_draft()
            self.root.bell()
            self.toggle_conversation(initial_message=text,acknowledge=not bool(text))

    def toggle_conversation(self,initial_message=None,acknowledge=False):
        if self.conversation:
            self.end_conversation();return
        if not self.voice_ready:
            self.status.set('Voice recognition is still loading. Text chat remains available.');return
        if self.busy or self.listening:
            self.status.set('Finish the current task or recording first.');return
        self.preserve_draft()
        self.conversation=True;self.speak_enabled.set(True)
        self.conversation_button.configure(text='End conversation')
        self.folder_button.configure(state='disabled');self.new_button.configure(state='disabled')
        self.append('Conversation mode','Hands-free conversation. Selected project: '+str(self.cwd)+'\nSpeak naturally and pause; Kesara sends the transcript automatically and listens again after replying. For project analysis, say "analyze the selected project." Stop ends the loop. File changes still require approval.','system')
        if initial_message:
            self.composer.insert('1.0',initial_message);self.send()
        elif acknowledge:
            self.append('Kesara',"Yes, I'm listening.",'kesara')
            self.speak("Yes, I'm listening.")
        else:self.maybe_listen()

    def end_conversation(self):
        self.conversation=False;self.pending_voice_send=False;self.review_voice_pending=False
        self.conversation_button.configure(text='Start conversation')
        self.mic_stop.set();self.speaker.stop();self.speech_id+=1;self.speech_in_progress=False
        self.expression('thinking' if self.busy else 'idle')
        if not self.busy and not self.listening:
            self.folder_button.configure(state='normal');self.new_button.configure(state='normal')
        self.status.set('Conversation ended. Name activation remains on.' if self.hands_free else 'Conversation ended. Microphone off; any running task can be stopped with Stop.')

    def maybe_listen(self):
        if self.alive and self.conversation and not self.review_voice_pending and self.voice_ready and not self.busy and not self.listening and not self.speech_in_progress and self.pending is None:
            self.toggle_mic()

    def stream_reply(self,text):
        self.chat.configure(state='normal')
        if not self.streaming_reply:
            self.chat.insert('end','KESARA\n',('label','kesara'))
            self.chat.mark_set('reply_start','end-1c')
            self.chat.mark_gravity('reply_start','left')
            self.streaming_reply=True
        ranges=self.chat.tag_ranges('current_reply')
        if ranges:self.chat.delete(ranges[0],ranges[-1])
        self.chat.insert('reply_start',text,('kesara','current_reply'))
        self.chat.configure(state='disabled');self.chat.see('end')

    def finish_stream(self):
        if not self.streaming_reply:return
        self.chat.configure(state='normal')
        ranges=self.chat.tag_ranges('current_reply')
        self.chat.insert(ranges[-1] if ranges else 'reply_start','\n\n','kesara')
        self.chat.tag_remove('current_reply','1.0','end')
        self.chat.mark_unset('reply_start')
        self.chat.configure(state='disabled');self.streaming_reply=False

    def set_busy(self,value):
        self.busy=value
        state='disabled' if value else 'normal'
        for button in (self.folder_button,self.new_button,self.mic_button): button.configure(state=state)
        self.send_button.configure(text='Stop' if value else 'Send  →',state='normal')
        if not self.voice_ready: self.mic_button.configure(state='disabled')
        if self.conversation:
            self.folder_button.configure(state='disabled');self.new_button.configure(state='disabled')
        if value:self.expression('thinking')

    def primary_action(self):
        if self.busy:
            if self.conversation:self.end_conversation()
            self.stop(); self.send_button.configure(text='Stopping...',state='disabled')
        else: self.send()

    def send(self):
        if self.busy or self.listening:
            diagnostic('send_blocked',busy=self.busy,listening=self.listening)
            return 'break'
        text=self.composer.get('1.0','end').strip()
        if not text: return 'break'
        diagnostic('request_submitted',characters=len(text),conversation=self.conversation)
        self.review_voice_pending=False
        self.composer.delete('1.0','end')
        self.append('You',text,'you')
        # Keep the actual selected folder visible alongside the user's request.
        self.status.set('Working in project: '+str(self.cwd))
        if text.startswith('/remember '):
            memory=json.loads(core.MEMORY.read_text(encoding='utf-8')) if core.MEMORY.exists() else []
            memory.append(text[10:]); core.MEMORY.write_text(json.dumps(memory,indent=2),encoding='utf-8')
            self.append('Kesara','Saved to memory.','kesara'); return 'break'
        self.speaker.stop()
        self.voice_reply_full=None;self.voice_reply_visible='';self.voice_reply_target='';self.voice_playback_started=False
        self.speech_id+=1;self.speech_in_progress=False
        if self.speech_stream_queue is not None:self.speech_stream_queue.put(None)
        self.speech_stream_queue=None;self.speech_stream_cursor=0
        self.cancelled.clear()
        self.set_busy(True)
        cwd=self.cwd
        def work():
            try: core.run_turn(text,self.messages,cwd,self.emit,self.confirm,self.cancelled)
            except Exception as exc: self.emit('error',str(exc))
            finally: self.emit('done',None)
        threading.Thread(target=work,daemon=True).start()
        return 'break'

    def confirm(self,description):
        if self.approval_policy.allows(self.cwd,description):
            diagnostic('approval_auto_granted',scope=self.approval_policy.mode(self.cwd))
            return True
        event=threading.Event()
        decision={'allow':False}
        self.emit('approval',(description,event,decision))
        while not event.wait(0.15):
            if self.cancelled.is_set() or not self.alive: return False
        return decision['allow'] and not self.cancelled.is_set()

    def approval(self,payload):
        description,event,decision=payload
        if self.cancelled.is_set(): event.set(); return
        self.pending=(event,decision)
        self.expression('approval')
        window=tk.Toplevel(self.root)
        self.approval_window=window
        window.title('Kesara — Review action')
        window.geometry('760x570')
        window.configure(bg=BG)
        window.transient(self.home.window if self.home else self.root)
        tk.Label(window,text='Review before allowing',font=('Segoe UI',18,'bold'),bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=(20,7))
        tk.Label(window,text='This action uses your Windows account. Inspect the full file or command below.',bg=BG,fg=MUTED).pack(anchor='w',padx=20,pady=(0,12))
        detail=scrolledtext.ScrolledText(window,bg=PANEL,fg=TEXT,wrap='word',font=('Consolas',10),relief='flat',padx=12,pady=12)
        detail.pack(fill='both',expand=True,padx=20)
        detail.insert('1.0',description); detail.configure(state='disabled')
        def finish(allow,scope='once'):
            if allow and scope!='once':
                kind,_=self.approval_policy.action_details(description)
                if kind=='shell':
                    label='for this session' if scope=='session' else 'persistently'
                    accepted=messagebox.askyesno('PowerShell permission',
                         'Allow arbitrary PowerShell commands '+label+' without future prompts? '
                         'PowerShell can access files outside this project.',parent=window)
                    if not accepted:return
                self.approval_policy.grant(self.cwd,description,scope)
                self.refresh_permission_policy()
            decision['allow']=allow; event.set()
            self.pending=None; self.approval_window=None
            window.destroy()
        bar=tk.Frame(window,bg=BG); bar.pack(fill='x',padx=20,pady=18)
        self.button(bar,'Decline',lambda:finish(False)).pack(side='left')
        self.button(bar,'Allow once',lambda:finish(True),accent=True).pack(side='left',padx=8)
        kind,_=self.approval_policy.action_details(description)
        if kind:
            self.button(bar,'Allow session',lambda:finish(True,'session')).pack(side='left',padx=8)
            self.button(bar,'Always allow',lambda:finish(True,'always')).pack(side='left',padx=8)
        window.protocol('WM_DELETE_WINDOW',lambda:finish(False))
        window.grab_set()
        self.status.set('Waiting for your approval')

    def stop(self):
        self.speech_id+=1;self.speech_in_progress=False
        if self.speech_stream_queue is not None:self.speech_stream_queue.put(None)
        self.speech_stream_queue=None;self.speech_stream_cursor=0
        self.cancelled.set()
        self.speaker.stop()
        if self.pending:
            event,decision=self.pending; decision['allow']=False; event.set(); self.pending=None
        if self.approval_window:
            self.approval_window.destroy(); self.approval_window=None
        if self.busy: self.status.set('Stopping after the current model request or running command finishes...')

    def choose_folder(self):
        if self.busy or self.listening or self.conversation:
            self.status.set('End voice chat before switching project folders.');return
        selected=filedialog.askdirectory(initialdir=str(self.cwd),title='Choose Kesara project folder')
        if selected:
            self.cwd=Path(selected).resolve(); self.folder_text.set(str(self.cwd)); self.messages=[]
            self.refresh_permission_policy()
            self.history.set_project(self.conversation_id,self.cwd)
            self.append('Workspace','Working in '+str(self.cwd),'system')

    def new_chat(self):
        if self.busy or self.listening: return
        self.conversation_id=self.history.create(self.cwd)
        self.load_conversation(self.conversation_id)

    def memory(self):
        window=tk.Toplevel(self.root); window.title('Kesara — Saved memory'); window.geometry('650x440'); window.configure(bg=BG)
        tk.Label(window,text='Saved memory',bg=BG,fg=TEXT,font=('Segoe UI',18,'bold')).pack(anchor='w',padx=18,pady=(18,6))
        tk.Label(window,text='One preference per line. Edit or remove anything you no longer want saved.',bg=BG,fg=MUTED).pack(anchor='w',padx=18,pady=(0,12))
        editor=scrolledtext.ScrolledText(window,bg=PANEL,fg=TEXT,insertbackground=TEXT,wrap='word',padx=10,pady=10)
        editor.pack(fill='both',expand=True,padx=18)
        values=json.loads(core.MEMORY.read_text(encoding='utf-8')) if core.MEMORY.exists() else []
        editor.insert('1.0','\n'.join(values))
        def save():
            values=[line.strip() for line in editor.get('1.0','end').splitlines() if line.strip()]
            core.MEMORY.write_text(json.dumps(values,indent=2),encoding='utf-8')
            window.destroy(); self.status.set('Memory saved locally')
        self.button(window,'Save memory',save,accent=True).pack(anchor='e',padx=18,pady=15)

    def export(self):
        target=filedialog.asksaveasfilename(title='Export conversation',defaultextension='.txt',filetypes=[('Text file','*.txt')])
        if target: Path(target).write_text(self.chat.get('1.0','end'),encoding='utf-8')

    def settings(self):
        window=tk.Toplevel(self.root); window.title('Kesara — Settings'); window.geometry('440x350'); window.configure(bg=BG)
        tk.Label(window,text='Settings',bg=BG,fg=TEXT,font=('Segoe UI',18,'bold')).pack(anchor='w',padx=20,pady=(20,12))
        tk.Checkbutton(window,text='Speak replies aloud',variable=self.speak_enabled,bg=BG,fg=TEXT,selectcolor=CARD,activebackground=BG,activeforeground=TEXT,command=self.speech_toggle).pack(anchor='w',padx=20,pady=(0,15))
        def open_panel(command): window.destroy(); command()
        self.button(window,'Choose microphone',lambda:open_panel(self.voice_settings)).pack(fill='x',padx=20,pady=5)
        self.button(window,'Saved memory',lambda:open_panel(self.memory)).pack(fill='x',padx=20,pady=5)
        self.button(window,'Export conversation',lambda:open_panel(self.export)).pack(fill='x',padx=20,pady=5)
        tk.Label(window,text='Talk interrupts a spoken reply.\nSend changes to Stop while a task is running.',bg=BG,fg=MUTED,justify='left').pack(anchor='w',padx=20,pady=12)

    def voice_settings(self):
        window=tk.Toplevel(self.root); window.title('Kesara — Voice settings'); window.geometry('680x830'); window.configure(bg=BG)
        tk.Label(window,text='Offline voice',bg=BG,fg=TEXT,font=('Segoe UI',18,'bold')).pack(anchor='w',padx=20,pady=(20,10))
        tk.Label(window,text='English voice · Windows default speaking voice\nTalk starts a conversation.\nMore offers optional name activation and camera gestures.',bg=BG,fg=MUTED,justify='left').pack(anchor='w',padx=20,pady=(0,15))
        try: devices=microphones()
        except Exception as exc: messagebox.showerror('Microphone unavailable',str(exc),parent=window); devices=[]
        labels=['Windows default microphone']+[f'{i}: {name}' for i,name in devices]
        choice=ttk.Combobox(window,values=labels,state='readonly',width=70)
        choice.current(0 if self.device is None else next((n+1 for n,(i,_) in enumerate(devices) if i==self.device),0))
        choice.pack(padx=20,fill='x')
        tk.Label(window,text='Names and technical words (comma-separated)',bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=(18,5))
        names=tk.Entry(window,bg=CARD,fg=TEXT,insertbackground=TEXT,relief='flat')
        names.pack(padx=20,fill='x',ipady=6)
        names.insert(0,', '.join(recognition_names()))
        tk.Label(window,text='Recognition hints only. They do not rename you or change your message.',bg=BG,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',padx=20,pady=(5,0))
        tk.Label(window,text='Recognition speed',bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=(12,4))
        speed=ttk.Combobox(window,values=['Balanced (faster)','Accurate (slower)'],state='readonly',width=30)
        try:voice_options=json.loads(VOICE_SETTINGS.read_text(encoding='utf-8'))
        except (OSError,ValueError):voice_options={}
        speed.current(0 if voice_options.get('recognition_mode')=='balanced' else 1);speed.pack(anchor='w',padx=20)
        tk.Label(window,text='Offline speech engine',bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=(12,4))
        engine_choice=ttk.Combobox(window,values=['Whisper (existing)','NVIDIA Parakeet V3 (free, local CPU)'],
                                   state='readonly',width=52)
        engine_choice.current(1 if voice_options.get('speech_engine')=='parakeet' else 0)
        engine_choice.pack(anchor='w',padx=20)
        tk.Label(window,text='Parakeet uses the optional sherpa-onnx package and downloads its model on first launch.',
                 bg=BG,fg=MUTED,wraplength=600).pack(anchor='w',padx=20)
        tk.Label(window,text='Whisper model (used when Whisper is selected)',bg=BG,fg=TEXT).pack(anchor='w',padx=20,pady=(12,4))
        model_choice=ttk.Combobox(window,values=['Small English (fast, less accurate)','Medium English (more accurate, slower CPU)'],
                                  state='readonly',width=52)
        model_choice.current(1 if voice_options.get('speech_model')=='medium.en' else 0)
        model_choice.pack(anchor='w',padx=20)
        review_value=tk.BooleanVar(value=bool(voice_options.get('review_transcripts',False)))
        tk.Checkbutton(window,text='Review spoken text before sending (safer for coding tasks)',variable=review_value,
                       bg=BG,fg=TEXT,selectcolor=CARD,activebackground=BG,activeforeground=TEXT).pack(anchor='w',padx=20,pady=(9,0))
        tk.Label(window,text='Medium is free but needs a larger download and more CPU/RAM. Restart Kesara after changing.',
                 bg=BG,fg=MUTED,wraplength=600).pack(anchor='w',padx=20)
        tk.Label(window,text='Correct frequently misheard names or technical terms',
                 bg=BG,fg=TEXT,font=('Segoe UI',10,'bold')).pack(anchor='w',padx=20,pady=(15,4))
        tk.Label(window,text='One correction per line: what Kesara heard => what you actually said. Local only.',
                 bg=BG,fg=MUTED,wraplength=600).pack(anchor='w',padx=20,pady=(0,5))
        corrections=tk.Text(window,height=5,bg=CARD,fg=TEXT,insertbackground=TEXT,relief='flat',
                            font=('Consolas',10),wrap='word')
        corrections.pack(fill='x',padx=20)
        corrections.insert('1.0',voice_options.get('speech_corrections',''))
        def save():
            n=choice.current(); self.device=None if n==0 else devices[n-1][0]
            values=[value.strip()[:60] for value in names.get().split(',') if value.strip()][:30]
            voice_options.update(recognition_names=values,recognition_mode='accurate' if speed.current()==1 else 'balanced',microphone_name=devices[n-1][1] if n>0 else None,speech_model='medium.en' if model_choice.current()==1 else 'small.en',speech_engine='parakeet' if engine_choice.current()==1 else 'whisper',review_transcripts=review_value.get())
            voice_options['speech_corrections']=format_corrections(parse_corrections(corrections.get('1.0','end')))
            VOICE_SETTINGS.write_text(json.dumps(voice_options,indent=2),encoding='utf-8')
            window.destroy(); self.status.set('Voice settings saved. Restart Kesara to load the selected speech model.')
        self.button(window,'Save voice settings',save,accent=True).pack(anchor='e',padx=20,pady=20)

    def toggle_mic(self):
        if self.busy or not self.voice_ready: return
        if self.listening:
            self.mic_stop.set(); self.mic_button.configure(state='disabled'); self.status.set('Finishing dictation...'); return
        self.ambient.configure(None)
        self.speaker.stop(); self.listening=True; self.user_speaking=False; self.mic_stop.clear()
        self.speech_id+=1;self.speech_in_progress=False
        self.expression('listening')
        self.recording_seconds=0
        self.mic_button.configure(text='■  Done')
        self.send_button.configure(state='disabled'); self.new_button.configure(state='disabled'); self.folder_button.configure(state='disabled')
        self.status.set('Listening for your voice...')
        device=self.device
        automatic=self.conversation
        def work():
            try: record(self.mic_stop,self.emit,device,auto_end=automatic)
            except Exception as exc:
                diagnostic('recording_error',error=str(exc))
                self.emit('voice_error',str(exc))
            finally: self.emit('mic_done',None)
        threading.Thread(target=work,daemon=True).start()

    def speech_toggle(self):
        if not self.speak_enabled.get():
            self.speaker.stop();self.speech_id+=1;self.speech_in_progress=False
            self.root.after(500,self.maybe_listen)

    @staticmethod
    def spoken_prose(text):
        """Convert response to speech without truncating its explanation."""
        # Never read full code blocks aloud; they remain available in chat.
        cleaned=re.sub(r'```[\s\S]*?```', ' Code example is available in chat. ', text)
        cleaned=re.sub(r'(?m)^#{1,6}\s+', '', cleaned)
        cleaned=re.sub(r'[*_`]', '', cleaned)
        return cleaned.strip()

    def stream_speech(self,text,final=False):
        if final:self.last_spoken_reply=self.spoken_prose(text)
        if not self.conversation or not self.speak_enabled.get():return False
        safe=self.spoken_prose(text)
        if final:
            if self.speech_stream_queue is None:return False
            remainder=safe[self.speech_stream_cursor:].strip()
            if remainder:self.speech_stream_queue.put(remainder)
            self.speech_stream_queue.put(None);self.speech_stream_queue=None
            return True
        ends=[match.end() for match in re.finditer(r'[.!?]\s+',safe)]
        if not ends:return False
        end=ends[-1]
        segment=safe[self.speech_stream_cursor:end].strip()
        if len(segment)<24:return False
        if self.speech_stream_queue is None:
            speech_queue=queue.Queue();self.speech_stream_queue=speech_queue
            self.speech_id+=1;identifier=self.speech_id
            self.speech_in_progress=True;self.expression('speaking')
            def work():
                try:
                    while self.alive and identifier==self.speech_id:
                        try:part=speech_queue.get(timeout=.2)
                        except queue.Empty:continue
                        if part is None:break
                        if identifier!=self.speech_id:break
                        self.emit('speech_chunk_started',(identifier,part))
                        self.speaker.speak(part)
                except Exception as exc:self.emit('voice_error',str(exc))
                finally:self.emit('speech_done',identifier)
            threading.Thread(target=work,daemon=True).start()
        self.speech_stream_queue.put(segment);self.speech_stream_cursor=end
        return True

    def speak(self,text):
        # Read the explanatory prose rather than an arbitrary 700-character cutoff.
        spoken=self.spoken_prose(text)
        self.last_spoken_reply=spoken
        if not spoken: return
        self.speech_id+=1;identifier=self.speech_id
        self.speech_in_progress=True;self.expression('speaking')
        def work():
            try:
                self.emit('speech_chunk_started',(identifier,spoken))
                self.speaker.speak(spoken)
            except Exception as exc: self.emit('voice_error',str(exc))
            finally:self.emit('speech_done',identifier)
        threading.Thread(target=work,daemon=True).start()

    def advance_voice_reply(self):
        """Reveal spoken text at conversational pace; flush on speech completion."""
        if not self.speech_in_progress or not self.conversation:
            self.voice_reply_tick_active=False
            return
        if not self.voice_playback_started:
            self.root.after(60,self.advance_voice_reply)
            return
        target=self.voice_reply_target
        if len(self.voice_reply_visible)<len(target):
            self.voice_reply_visible=target[:min(len(target),len(self.voice_reply_visible)+2)]
            self.stream_reply(self.voice_reply_visible)
        self.root.after(60,self.advance_voice_reply)

    def ensure_voice_reply_tick(self):
        if not self.voice_reply_tick_active:
            self.voice_reply_tick_active=True
            self.root.after(60,self.advance_voice_reply)

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='viseme':
                    if self.speech_in_progress and value and self.conversation:
                        self.voice_playback_started=True
                        self.ensure_voice_reply_tick()
                    self.viseme=value if self.speech_in_progress else 0
                    if hasattr(self.avatar,'viseme'):self.avatar.viseme=self.viseme
                elif kind=='standby_phase':
                    if value!='Say Kesara' or not self.standby_phase.startswith('Name missed'):self.standby_phase=value
                elif kind=='standby_heard':self.last_standby_heard=value
                elif kind=='ambient_wake':
                    if self.hands_free:self.wake_up(value)
                elif kind=='ambient_quiet':
                    if self.hands_free:self.quiet()
                elif kind=='ambient_error':
                    self.hands_free=False
                    self.append('Wake listening unavailable',value,'system')
                    self.status.set('Wake listening stopped. Open workspace for details.')
                elif kind=='camera_gesture':
                    if self.camera_enabled:
                        if value=='quiet':self.quiet()
                        else:self.wake_up()
                elif kind=='camera_state':
                    self.camera_active=value=='on'
                elif kind=='camera_error':
                    self.camera_enabled=False
                    self.append('Camera unavailable',value,'system')
                    self.status.set('Camera stopped. Open workspace for details.')
                elif kind=='status':
                    self.status.set(value)
                    if value.startswith('Thinking'):self.expression('thinking')
                    elif value.startswith('Listening'):self.expression('listening')
                elif kind=='assistant': self.append('Kesara',value,'kesara')
                elif kind=='answer':
                    if self.conversation and self.speak_enabled.get():
                        # Show speech in step with what Kesara is actually
                        # saying, instead of dumping the model's fast tokens.
                        self.voice_reply_full=value
                        self.ensure_voice_reply_tick()
                        self.history.add(self.conversation_id,'kesara',value)
                        self.refresh_history()
                        if not self.stream_speech(value,final=True):self.speak(value)
                    else:
                        if self.streaming_reply:
                            self.stream_reply(value);self.finish_stream()
                            self.history.add(self.conversation_id,'kesara',value)
                            self.refresh_history()
                        else:self.append('Kesara',value,'kesara')
                        if self.speak_enabled.get():
                            if not self.stream_speech(value,final=True):self.speak(value)
                        else:self.expression('idle')
                    self.status.set('Speaking...' if self.speech_in_progress else 'Ready')
                elif kind=='answer_partial':
                    if not self.conversation:self.stream_reply(value)
                    self.status.set('Preparing spoken reply...' if self.conversation else 'Replying...')
                    self.stream_speech(value)
                elif kind=='tool': self.append('Tool result',value,'tool')
                elif kind=='approval': self.approval(value)
                elif kind=='error':
                    if self.conversation:self.end_conversation()
                    self.expression('error')
                    self.append('Could not complete request',value,'system'); self.status.set('Request failed. You can try again.')
                elif kind=='done':
                    if self.speech_stream_queue is not None:
                        self.speech_stream_queue.put(None);self.speech_stream_queue=None
                    if not (self.conversation and self.voice_reply_full is not None):
                        self.finish_stream()
                    self.set_busy(False)
                    if len(self.messages)>24: self.messages=self.messages[-24:]
                    if not self.speech_in_progress:self.expression('idle')
                    self.root.after(500,self.maybe_listen)
                elif kind=='partial': self.status.set(f'Listening · {self.recording_seconds:.0f}s — '+('Heard: '+value[-100:] if value.strip() else 'speak a full sentence, then Done'))
                elif kind=='recording_seconds':
                    self.recording_seconds=value
                    self.status.set((f'Hearing you · {value:.0f}s — keep talking.' if self.user_speaking else f'Listening · {value:.0f}s — speak naturally.') if self.conversation else f'Listening · {value:.0f}s — speak, then click Done')
                elif kind=='speech_started':
                    self.user_speaking=True
                    self.expression('listening');self.status.set('Hearing your speech — keep talking.')
                elif kind=='speech_ended':
                    self.user_speaking=False
                    self.status.set('Speech ended — transcribing...')
                elif kind=='processing_voice':
                    self.expression('thinking')
                    self.status.set('Transcribing your speech locally...')
                    self.mic_button.configure(text='Transcribing...',state='disabled')
                elif kind=='no_speech':
                    if not self.conversation:self.append('Microphone check',value,'system')
                    self.status.set('Listening again shortly...' if self.conversation else value)
                elif kind=='level':
                    self.level.configure(value=value);self.avatar.set_level(value)
                    if self.companion and self.companion.winfo_exists():self.companion.set_level(value)
                elif kind=='voice_setup_status':
                    self.status.set(value)
                    self.mic_button.configure(text='Preparing voice...',state='disabled')
                elif kind=='voice_ready':
                    self.voice_ready=True
                    self.mic_button.configure(text='●  Talk',state='disabled' if self.busy else 'normal')
                    if not self.busy: self.status.set('Ready. Click Talk, wait for Listening, then speak.' if self.model_ready else 'Preparing the local AI. You can type while it loads.')
                elif kind=='model_ready':
                    self.model_ready=True
                    self.model_state.set('Qwen2.5-Coder · 3B\nReady · CPU mode')
                    if not self.busy and not self.listening:self.status.set('Ready. Local AI is loaded.')
                elif kind=='model_warm_error':
                    self.model_error=str(value)
                    self.model_state.set('Qwen2.5-Coder · 3B\nModel warm-up failed; check Ollama')
                    if not self.busy:self.status.set('AI model warm-up failed; first voice request may fail. Check Ollama.')
                elif kind=='voice_unavailable': self.mic_button.configure(text='Voice unavailable',state='disabled')
                elif kind=='dictation':
                    diagnostic('transcript_received',characters=len(value or ''),conversation=self.conversation)
                    if value and self.conversation:
                        # Avoid immediately feeding a repeated hallucination or
                        # speaker echo back into the agent as a new instruction.
                        normalized=' '.join(re.findall(r'[a-z0-9]+',value.lower()))
                        previous=' '.join(re.findall(r'[a-z0-9]+',self.last_voice_transcript.lower()))
                        spoken=' '.join(re.findall(r'[a-z0-9]+',self.last_spoken_reply.lower()))
                        now=time.monotonic()
                        if not normalized or (normalized==previous and now-self.last_voice_transcript_at<30) or (
                            len(normalized)>=12 and normalized in spoken and self.last_spoken_reply):
                            self.status.set('Ignored repeated/echoed audio; listening again.')
                            continue
                        self.last_voice_transcript=value
                        self.last_voice_transcript_at=now
                    if value:
                        if self.conversation and voice_command(value)=='quiet':
                            self.quiet();continue
                        if self.conversation and value.strip().lower().rstrip('.!?') in ('stop listening','end conversation','stop conversation'):
                            self.hands_free=False;self.ambient.configure(None)
                            self.end_conversation();continue
                        existing=self.composer.get('1.0','end').strip()
                        self.composer.insert('end',(' ' if existing else '')+value)
                        if self.conversation and not self.review_voice_pending:
                            try:review_enabled=bool(json.loads(VOICE_SETTINGS.read_text(encoding='utf-8')).get('review_transcripts',False))
                            except (OSError,ValueError):review_enabled=False
                            if review_enabled or requires_voice_review(value):
                                self.review_voice_pending=True
                                self.status.set('Voice command needs confirmation. Correct the transcript and press Send; no file action has run.')
                                self.root.deiconify();self.root.lift()
                            else:self.pending_voice_send=True
                        else:self.status.set('Check your message, then Send.')
                elif kind=='voice_error':
                    if self.conversation:self.end_conversation()
                    self.expression('error')
                    self.append('Voice unavailable',value+'\nYou can continue by typing. Check Voice settings or Windows microphone permissions.','system')
                    self.status.set('Voice issue — text chat remains available')
                elif kind=='mic_done':
                    diagnostic('voice_handoff',conversation=self.conversation,auto_send=self.pending_voice_send)
                    self.listening=False; self.user_speaking=False; self.mic_button.configure(text='●  Talk',state='normal')
                    self.level.configure(value=0)
                    self.send_button.configure(state='normal'); self.new_button.configure(state='normal'); self.folder_button.configure(state='normal')
                    self.expression('idle')
                    if self.conversation:
                        self.new_button.configure(state='disabled');self.folder_button.configure(state='disabled')
                        if self.pending_voice_send:
                            self.pending_voice_send=False;self.send()
                        elif self.review_voice_pending:
                            self.status.set('Transcript ready to review. Correct the text and press Send.')
                        else:self.root.after(500,self.maybe_listen)
                elif kind=='speech_chunk_started':
                    # Speech worker may emit before the final answer arrives.
                    # Display begins when the synthesizer produces real visemes.
                    identifier,part=value
                    if identifier==self.speech_id and self.conversation:
                        self.voice_reply_target+=(' ' if self.voice_reply_target else '')+part
                        self.ensure_voice_reply_tick()
                elif kind=='speech_done':
                    if value==self.speech_id:
                        if self.conversation and self.voice_reply_full is not None:
                            self.stream_reply(self.voice_reply_full)
                            self.finish_stream()
                            self.voice_reply_full=None;self.voice_reply_visible='';self.voice_reply_target='';self.voice_playback_started=False
                        self.speech_in_progress=False;self.expression('thinking' if self.busy else 'idle')
                        self.root.after(500,self.maybe_listen)
        except queue.Empty: pass
        if self.alive: self.root.after(60,self.poll)

    def close(self):
        self.ambient.close();self.camera.close()
        self.alive=False;self.conversation=False; self.mic_stop.set(); self.stop();self.speaker.close(); self.root.destroy()

def main():
    from companion import CompanionHome
    root=tk.Tk();root.withdraw()
    app=App(root);app.home=CompanionHome(app)
    if '--wake' in __import__('sys').argv:app.toggle_hands_free()
    root.mainloop()

if __name__=='__main__': main()
