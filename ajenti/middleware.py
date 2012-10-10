import hashlib
import time
import Cookie
import random

import ajenti
from ajenti.api import *
from ajenti.http import HttpHandler
from ajenti.users import UserManager


class Session:
    def __init__(self, id):
        self.touch()
        self.id = id
        self.data = {}

    def touch(self):
        self.timestamp = time.time()

    def is_dead(self):
        return (time.time() - self.timestamp) > 3600

    def start(self, context):
        C = Cookie.SimpleCookie()
        C['session'] = self.id
        C['session']['path'] = '/'
        context.add_header('Set-Cookie', C['session'].OutputString())


@plugin
class SessionMiddleware (HttpHandler):
    def __init__(self):
        self.sessions = {}

    def generate_session_id(self, context):
        hash = str(random.random())
        hash += context.env.get('REMOTE_ADDR', '')
        hash += context.env.get('REMOTE_HOST', '')
        hash += context.env.get('HTTP_USER_AGENT', '')
        hash += context.env.get('HTTP_HOST', '')
        return hashlib.sha1(hash).hexdigest()

    def vacuum(self):
        for session in [x for x in self.sessions.values() if x.is_dead()]:
            del self.sessions[session.id]

    def open_session(self, context):
        session_id = self.generate_session_id(context)
        session = Session(session_id)
        session.start(context)
        self.sessions[session_id] = session
        return session

    def handle(self, context):
        self.vacuum()
        cookie = Cookie.SimpleCookie(context.env.get('HTTP_COOKIE')).get('session')
        if cookie is not None and cookie.value in self.sessions:
            context.session = self.sessions[cookie.value]
        else:
            context.session = self.open_session(context)
        context.session.touch()


@plugin
class AuthenticationMiddleware (HttpHandler):
    def handle(self, context):
        if not hasattr(context.session, 'identity'):
            if ajenti.config.tree.authentication:
                context.session.identity = None
            else:
                context.session.identity = ajenti.config.tree.users.keys()[0]
                context.session.appcontext = AppContext(context)

    def try_login(self, context, username, password):
        if UserManager.get().check_password(username, password):
            context.session.identity = username
            context.session.appcontext = AppContext(context)
            return True
        return False

    def logout(self, context):
        context.session.identity = None
