# -*- coding: utf-8 -*-
'''
Copyright (c) 2017, Jairus Martin.

Distributed under the terms of the MIT License.

The full license is in the file COPYING.txt, distributed with this software.

@author jrm

'''
import os
import sys
import json
import shutil
from atom.api import Atom, ForwardInstance, Enum, Unicode, Int, Bool
from contextlib import contextmanager

@contextmanager
def cd(newdir):
    prevdir = os.getcwd()
    os.chdir(os.path.expanduser(newdir))
    try:
        print("Entering into {}".format(newdir))
        yield
        print("Returning to {}".format(prevdir))
    finally:
        os.chdir(prevdir)


INDEX_PAGE = """<html>
<head>
  <title>Enaml-Native Playground</title>
  <!--Import Google Icon Font-->
  <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">

  <!-- Compiled and minified CSS -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/css/materialize.min.css">
  <link rel="shortcut icon" href="https://www.codelv.com/static/faveicon.png">
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
</head>
<body>
  <div class="nav-fixed">
    <nav role="navigation" class="teal">
      <div class="nav-wrapper container">
        <a href="#" class="brand-logo">Enaml-Native Playground</a>
        <ul id="nav-mobile" class="right hide-on-med-and-down">
          <li><a href="https://www.codelv.com/projects/enaml-native/">Project</a></li>
          <li><a href="https://www.codelv.com/projects/enaml-native/docs/">Docs</a></li>
        </ul>
      </div>
    </nav>
  </div>
  <div id="editor" style="height:100%;width:100%;">
from enaml.core.api import *
from enamlnative.widgets.api import *


enamldef ContentView(LinearLayout):
    TextView:
        text = "Test!"

  </div> <!-- code -->

  <div class="fixed-action-btn">
    <a id="run" class="btn-floating btn-large blue" href="#">
       <i class="large material-icons">play_arrow</i>
     </a>
  </div>
  <footer class="page-footer teal">
    <div class="container">
      <div class="row">
        <div class="col l6 s12">
          <h5 class="white-text">Enaml-Native Playground</h5>
          <p class="grey-text text-lighten-4">Test out enaml native app code right from the browser!</p>
        </div>
        <div class="col l4 offset-l2 s12">
          <h5 class="white-text">Links</h5>
          <ul>
            <li><a class="grey-text text-lighten-3" href="https://www.codelv.com/projects/enaml-native/docs/">Docs</a></li>
            <li><a class="grey-text text-lighten-3" href="https://github.com/frmdstryr/enaml-native/">Code</a></li>
            <li><a class="grey-text text-lighten-3" href="https://www.codelv.com/projects/enaml-native/support/">Support</a></li>
          </ul>
        </div>
      </div>
    </div>
    <div class="footer-copyright">
      <div class="container">
        © 2017 <a href="https://www.codelv.com">codelv.com</a>
        <a class="grey-text text-lighten-4 right" href="https://www.codelv.com/projects/enaml-native/">Python powered native apps</a>
      </div>
    </div>
  </footer>

  <!--Import jQuery before materialize.js-->
  <script type="text/javascript" src="https://code.jquery.com/jquery-3.2.1.min.js"></script>
  <!-- Compiled and minified JavaScript -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/materialize/0.100.2/js/materialize.min.js"></script>
  <!-- Editor -->
  <script src="https://cdnjs.cloudflare.com/ajax/libs/ace/1.2.8/ace.js"></script>
  <script type="text/javascript">
    $(document).ready(function(){
        var editor = ace.edit("editor");
        editor.setTheme("ace/theme/github");
        editor.getSession().setMode("ace/mode/python");

        var enaml;
        $('#run').click(function(e){
            try {
                // Trigger a reload
                enaml.send(JSON.stringify({
                    'type':'reload',
                    'files':{
                        'view.enaml':editor.getValue(),
                    }
                }));
            } catch (ex) {
                console.log(ex);
            }
        });
        var connect = function(){
            var url = "ws://"+window.location.hostname+":8888/dev";
            enaml = new WebSocket(url);

            enaml.onopen = function(e) {
                console.log("Connected");
            }
            enaml.onmessage = function(e) {

            }
            enaml.onclose = function(e) {
                console.log("Disconnected");
                connect();
            }
        }
        connect();
    });
  </script>
</body>
</html>"""


def get_app():
    from .app import BridgedApplication
    return BridgedApplication


class DevServerSession(Atom):
    """ Connect to a dev server running on the LAN
        or if host is 0.0.0.0 server a page to let
        code be pasted in. Note this should NEVER be used
        in a released app!
    """
    _instance = None
    app = ForwardInstance(get_app)
    host = Unicode()
    port = Int(8888)
    url = Unicode('ws://192.168.21.119:8888/dev')
    connected = Bool()
    buf = Unicode()
    mode = Enum('client', 'server')

    def _default_url(self):
        return 'ws://{}:{}/dev'.format(self.host,self.port)

    def _default_app(self):
        return get_app().instance()

    @classmethod
    def initialize(cls,*args, **kwargs):
        try:
            return DevServerSession(*args, **kwargs)
        except ImportError:
            #: TODO: Try twisted
            pass

    @classmethod
    def instance(cls):
        return DevServerSession._instance

    def __init__(self, *args, **kwargs):
        if self.instance() is not None:
            raise RuntimeError("A DevServerClient instance already exists!")
        super(DevServerSession, self).__init__(*args, **kwargs)
        DevServerSession._instance = self

    def _default_mode(self):
        """ If host is set to server then serve it from the app! """
        return "server" if self.host=="server" else "client"

    def start(self):
        print("Starting debug client cwd: {}".format(os.getcwd()))
        print("Sys path: {}".format(sys.path))
        if self.mode=='client':
            try:
                self.start_tornado_client()
            except ImportError:
                self.start_twisted_client()
        else:
            try:
                self.start_tornado_server()
            except ImportError:
                self.start_twisted_server()

    def start_tornado_server(self):
        """ Run a server in the app and host a page that does what the dev server does """
        import tornado.ioloop
        import tornado.web
        import tornado.websocket
        ioloop = tornado.ioloop.IOLoop.current()
        server = self

        class DevWebSocketHandler(tornado.websocket.WebSocketHandler):
            def open(self):
                print("Dev server client connected!")

            def on_message(self, message):
                server.handle_message(message)

            def on_close(self):
                print("Dev server client lost!")


        class MainHandler(tornado.web.RequestHandler):
            def get(self):
                self.write(INDEX_PAGE)

        app = tornado.web.Application([
            (r"/", MainHandler),
            (r"/dev", DevWebSocketHandler),
        ])

        #: Start listening
        app.listen(self.port)

    def start_tornado_client(self):
        """ Connect to a dev server running on a pc. """
        from tornado.websocket import websocket_connect
        from tornado import gen

        @gen.coroutine
        def run():
            try:
                print("Dev server connecting {}...".format(self.url))
                conn = yield websocket_connect(self.url)
                self.connected = True
                while True:
                    msg = yield conn.read_message()
                    if msg is None: break
                    self.handle_message(msg)
                self.connected = False
            except Exception as e:
                print("Dev server connection dropped: {}".format(e))
            finally:
                #: Try again in a few seconds
                self.app.timed_call(1000, run)

        #: Start
        self.app.deferred_call(run)

    def start_twisted_client(self):
        #: TODO:...
        raise NotImplementedError

    def start_twisted_server(self):
        #: TODO:...
        raise NotImplementedError

    def _observe_connected(self, change):
        print("Dev server {}".format("connected" if self.connected else "disconnected"))

    def handle_message(self, data):
        """ When we get a message """
        msg = json.loads(data)
        print("Dev server message: {}".format(msg))
        if msg['type'] == 'reload':
            #: Show loading screen
            self.app.widget.showLoading("Reloading... Please wait.", now=True)

            with cd(sys.path[0]):
                #: Clear cache
                if os.path.exists('__enamlcache__'):
                    shutil.rmtree('__enamlcache__')
                for fn in msg['files']:
                    print("Updating {}".format(fn))
                    with open(fn, 'w') as f:
                        f.write(msg['files'][fn])

            self.app.reload()