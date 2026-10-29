"""Vercel Python function entry point."""
import os
import sys
from pathlib import Path
from threading import Lock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import Handler, initialize

_ready=False
_lock=Lock()
_login_attempts={}

class handler(Handler):
    def api(self,method,path,body):
        global _ready
        if not os.environ.get('DATABASE_URL') or not os.environ.get('TEACHER_PASSWORD'):
            return self.send_json(503,{'error':'Set DATABASE_URL and TEACHER_PASSWORD in Vercel environment settings before opening the classroom.'})
        try:
            with _lock:
                if not _ready:
                    initialize()
                    _ready=True
            self.server.login_attempts=_login_attempts
            return super().api(method,path,body)
        except Exception:
            return self.send_json(503,{'error':'Classroom storage is unavailable. Check database connectivity and configuration.'})
