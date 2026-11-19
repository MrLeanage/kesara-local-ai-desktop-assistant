"""Explicit, project-scoped human approval policies for Kesara desktop actions.

An approval policy is a convenience, not an OS security sandbox. PowerShell
can access resources outside the selected project; never grant it silently.
"""
import json
from pathlib import Path

MODES=('ask','session_write','session_all','always_write','always_all')
ACTION_TYPES=('write','mkdir','shell')

class ApprovalPolicy:
    def __init__(self, store):
        self.store=Path(store)
        self.sessions={}
        self.persisted={}
        try:
            document=json.loads(self.store.read_text(encoding='utf-8'))
            if isinstance(document,dict):
                self.persisted={str(key):value for key,value in document.items()
                                if value in ('always_write','always_all')}
        except (OSError,ValueError):
            pass

    @staticmethod
    def project_key(project):
        return str(Path(project).resolve()).casefold()

    def mode(self,project):
        key=self.project_key(project)
        return self.sessions.get(key,self.persisted.get(key,'ask'))

    def set_mode(self,project,mode):
        if mode not in MODES:
            raise ValueError('Unsupported approval policy')
        key=self.project_key(project)
        self.sessions.pop(key,None)
        self.persisted.pop(key,None)
        if mode.startswith('session_'):
            self.sessions[key]=mode
        if mode.startswith('always_'):
            self.persisted[key]=mode
        self.save()

    def save(self):
        self.store.parent.mkdir(parents=True,exist_ok=True)
        temp=self.store.with_name(self.store.name+'.tmp')
        temp.write_text(json.dumps(self.persisted,indent=2),encoding='utf-8')
        temp.replace(self.store)

    @staticmethod
    def action_details(description):
        if description.startswith('MKDIR '):
            return 'mkdir',description.split('\n',1)[0][6:].strip()
        if description.startswith('WRITE '):
            return 'write',description.split('\n',1)[0][6:].strip()
        if description.startswith('RUN PowerShell in '):
            return 'shell',None
        # Reads outside the project must never receive blanket approval.
        return None,None

    def allows(self,project,description):
        kind,target=self.action_details(description)
        if kind is None:
            return False
        if kind in ('write','mkdir'):
            if not target:
                return False
            root=Path(project).resolve()
            try:
                path=Path(target).resolve()
                if not path.is_relative_to(root):
                    return False
            except (OSError,ValueError):
                return False
        mode=self.mode(project)
        if mode in ('session_all','always_all'):
            return True
        return kind in ('write','mkdir') and mode in ('session_write','always_write')

    def grant(self,project,description,scope):
        kind,target=self.action_details(description)
        if kind is None or scope=='once':
            return
        if scope not in ('session','always'):
            raise ValueError('Unsupported grant scope')
        if kind in ('write','mkdir'):
            new_mode='session_write' if scope=='session' else 'always_write'
        else:
            new_mode='session_all' if scope=='session' else 'always_all'
        self.set_mode(project,new_mode)
