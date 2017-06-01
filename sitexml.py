# -*- coding: utf-8 -*-

"""
SiteXML parser


MIT License

Copyright (c) 2017 Roman Mindlin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from urllib.parse import parse_qs
from html import escape
from beaker.middleware import SessionMiddleware

DEBUG = True
SITEXML = '.site.xml'
USERS_FILE = '../.users'
CONTENT_DIR = '.content/'
THEMES_DIR = '.themes/'
MODULES_DIR = '.modules/'
AJAX_BROWSING_SCRIPT = '<script src="/js/siteXML.ajaxBrowsing.js"></script>'
CONTENT_EDIT_SCRIPT = '''
    <link rel="stylesheet" href="http://yui.yahooapis.com/3.18.1/build/cssreset-context/cssreset-context-min.css" type="text/css" />
    <link rel="stylesheet" href="/css/siteXML.editContent.css" type="text/css" />
    <link rel="stylesheet" href="/css/siteXML.editXML.css" type="text/css" />
    <script src="/js/siteXML.editContent.js"></script>
    <script src="/js/siteXML.editXML.js"></script>
    '''
DEFAULT_THEME_HTML = '''
    <!DOCTYPE html><html>
    <head><meta http-equiv="Content-Type" content="text/html; charset=utf8">
    <%META%>
    <title><%TITLE%></title>
    </head><body>
    <div id="header" style="font-size: 3em"><%SITENAME%></div><div id="navi" style="float:left; width:180px"><%NAVI%></div>
    <div id="main" style="padding:0 10px 20px 200px"><%CONTENT(main)%></div>
    <div id="footer">This is <a href="http://www.sitexml.info">SiteXML</a> default theme<br/>SiteXML:PHP v1.0
    <a href="/.site.xml">.site.xml</a></div></body></html>
    '''


class SiteXML():
    def __init__(self):

        self._response_headers = []
        self._response_body = ''

        self.editMode = False

        self.setEditMode()
        self.obj = self.getObj()
        self.pid = self.getPid()
        self.pageObj = self.getpageObj(self.pid)
        self.themeObj = self.getTheme()
        self.basePath = self.getSiteBasePath()

    @property
    def response_headers(self):
        return self._response_headers

    @response_headers.setter
    def response_headers(self, header):
        self._response_headers.append(header)

    @property
    def response_body(self):
        return self._response_body

    @response_body.setter
    def response_body(self, content):
        self._response_body += content

    def setEditMode(self):
        if (not session.get('edit', None)) and (not session.get('username', None)):
            self.response_headers = ('Cache-Control', 'no-cache, must-revalidate')
            self.editMode = True


def app(environ, start_response):
    global session

    session = environ['beaker.session']

    sitexml = SiteXML()

    status = '200 OK'
    response_headers = [
        ('Content-Type', 'text/html; charset=utf-8'),
    ]

    method = environ['REQUEST_METHOD']
    if method == 'POST':
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except (ValueError):
            request_body_size = 0

        request_body = environ['wsgi.input'].read(request_body_size)
        d = parse_qs(request_body)

        if 'sitexml' in d:
            if sitexml.saveXML(d.get('sitexml')):
                sitexml.response_body = 'siteXML saved'
            else:
                sitexml.response_body = sitexml.error('siteXML was not saved')
        elif ('cid' in d) and ('content' in d):
            sitexml.response_body = sitexml.saveContent(d.get('cid'), d.get('content'))
        elif ('username' in d) and ('password' in d):
            sitexml.response_body = sitexml.login()

    elif method == 'GET':
        d = parse_qs(environ['QUERY_STRING'])

        if 'logout' in d:
            sitexml.response_body = sitexml.logout()

        if 'edit' in d:
            if not d.get('username', None):
                session['edit'] = True
                sitexml.response_body = sitexml.page()
            else:
                sitexml.response_body = sitexml.loginScreen('edit')
        elif 'sitexml' in d:
            sitexml.response_headers = [
                ('Content-Type', 'text/xml; charset=utf-8'),
            ]
            sitexml.response_body = sitexml.getXML()
        elif 'login' in d:
            sitexml.response_body = sitexml.loginScreen()
        elif not d.get('cid', None):
            sitexml.response_body = sitexml.getContent(d.get('cid'))
        elif (not d.get('id', None)) and (not d.get('name', None)):
            sitexml.response_body = sitexml.getContentByIdAndName(d.get('id'), d.get('name'))
        else:
            sitexml.response_body = sitexml.page()

    else:
        status = '405 Method Not Allowed'
        sitexml.response_headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Allow', 'GET, POST'),
        ]

    start_response(status, sitexml.response_headers)
    return [sitexml.response_body]


if __name__ == '__main__':
    try:
        from wsgiref.simple_server import make_server

        session_opts = {
            'session.auto': True,
            'session.type': 'cookie',
            'session.cookie_expires': True,
            'session.httponly': True,
            'session.secure': True
        }
        wsgi_app = SessionMiddleware(app, session_opts)

        httpd = make_server('', 8080, wsgi_app)
        print('Serving on port 8080...')
        httpd.serve_forever()

    except KeyboardInterrupt:
        print('Goodbye.')
