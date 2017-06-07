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

import os
import hashlib
from urllib.parse import parse_qs, unquote_plus
from html import escape
import xml.etree.ElementTree as ET
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


class SiteXML:
    def __init__(self, environ):

        self.environ = environ
        self.session = environ['beaker.session']

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
        self._response_headers.update(header)

    @property
    def response_body(self):
        return self._response_body

    @response_body.setter
    def response_body(self, content):
        self._response_body += content

    def setEditMode(self):
        if (not self.session.get('edit')) and (not self.session.get('username')):
            self.response_headers = ('Cache-Control', 'no-cache, must-revalidate')
            self.editMode = True

    def loginScreen(self, edit=''):
        self.response_body = '''
        <!DOCTYPE html>
<html>
<head>
    <title>Login</title>
</head>
<style>
    .siteXML-logindiv {
        width: 250px;
        margin: auto;
    }
    .siteXML-logindiv div {
        padding: 5px 0;
    }
</style>
<body>
<div class="siteXML-logindiv">
    <form action="/" method="post">
        <div>
            <input placeholder="Username" name="username" type="text" autofocus="true">
        </div>
        <div>
            <input placeholder="Password" name="password" type="password">
        </div>
        <div>
        '''
        if edit == 'edit':
            self.response_body = '<input type="hidden" name="edit" value="true">'
        self.response_body = '''
        <input type="submit">
        </div>
    </form>
</div>
</body>
</html>
        '''

    def login(self, username, password, edit):
        m = hashlib.md5()

        password = m.update(password).hexdigest()
        user = self.getUser(username)
        if user:
            if user[2] == password:
                self.session['username'] = username
                if edit:
                    self.session['edit'] = True
                self.response_headers = ('location', '/')

    @staticmethod
    def getUser(username):
        if os.path.isfile(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                for user in f.readline():
                    user = user.split(':')
                    if user[1] == username:
                        return user

    def logout(self):
        self.session.delete()

    @staticmethod
    def getObj():
        if os.path.isfile(SITEXML):
            return ET.parse(SITEXML).getroot()
        else:
            raise FileNotFoundError

    def getPid(self):
        pid = None
        d = parse_qs(self.environ['QUERY_STRING'])

        if 'id' in d:
            pid = d['id']
        elif self.environ['PATH_INFO'] != '/':
            if self.environ['PATH_INFO'][0] == '/':
                alias = self.environ['PATH_INFO'][1:]
            else:
                alias = self.environ['PATH_INFO']

            alias = unquote_plus(alias)
            aliasNoEndingSlash = alias.rstrip('/')
            pid = self.getPageIdByAlias(aliasNoEndingSlash)

        if not pid:
            defaultPid = self.getDefaultPid()
            if not defaultPid:
                defaultPid = self.getFirstPagePid()
            pid = defaultPid

        if not pid:
            raise RuntimeError('Fatal error: no pages in this site')
        else:
            return pid

    # recursive
    def getDefaultPid(self, pageObj=None):
        if not pageObj:
            pageObj = self.obj
        defaultPid = None
        for v, k in enumerate(pageObj):
            if k.lower() == 'page':
                attr = self.attributes(v)
                if attr['startpage'] == 'yes':
                    defaultPid = attr['id']
                    break
                else:
                    defaultPid = self.getDefaultPid(v)
                    if defaultPid:
                        break
        return defaultPid

    " @ param {String} $alias - make sure that it doesn't end with slash - ' / ' "

    def getPageIdByAlias(self, alias, parent=None):
        pid = None
        if not parent:
            parent = self.obj
        for v, k in enumerate(parent):
            if k.lower() == 'page':
                attr = self.attributes(v)
                if (not attr.get('alias')) and attr.get('alias').rstrip() == alias:
                    pid = attr['id']
                else:
                    pid = self.getPageIdByAlias(alias, v)
                if pid:
                    break
        return pid

    def getFirstPagePid(self):
        pid = None
        for v, k in enumerate(self.obj):
            if k.lower() == 'page':
                attr = self.attributes(v)
                pid = attr['id']
                break
        return pid

    def getPageObj(self, pid):
        if pid:
            pageObj = self.obj.findall("//page[@id='$pid']")
        else:
            pageObj = self.obj.findall("//page")
        if pageObj:
            return pageObj[0]
        else:
            return None

    """
     param {Object} page object.If not given, $this->pageObj will be used
     returns {Object} theme by page object
    """

    def getTheme(self, pageObj=None):
        if not pageObj:
            pageObj = self.pageObj()
        attr = self.attributes(pageObj)
        themeId = attr.get('theme')
        if themeId:
            themeObj = self.obj.findall("//theme[@id='$themeId']")
            if not themeObj:
                self.error("Error: theme with id $themeId does not exist")
        else:
            themeObj = self.obj.findall(
                "//theme[contains(translate(@default, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')]")
            if not themeObj:
                themeObj = self.obj.findall("//theme")
        if themeObj:
            return themeObj[0]
        else:
            return None

    """
    @param {Object} theme || If not given, DEFAULT_THEME_HTML will be returned
    @returns {String} theme html
    """

    def getThemeHTML(self, themeObj=None):
        if not themeObj:
            self.error('SiteXML error: template does not exist, default template HTML will be used')
            themeHTML = DEFAULT_THEME_HTML
        else:
            attr = self.attributes(themeObj)
            dir_attr = '' if not attr.get('dir') else attr['dir']
            path = THEMES_DIR
            if path[-1] != '/':
                path += '/'
            if dir_attr != '': # meaningless
                path += dir_attr
            if path[-1] != '/':
                path += '/'
            if attr.get('file'):
                path += attr['file']
                if os.path.isfile(path):
                    with open(path, 'r') as f:
                        themeHTML = f.read()
                else:
                    self.error('SiteXML error: template file does not exist, default template HTML will be used')
                    themeHTML = DEFAULT_THEME_HTML
            else:
                self.error('SiteXML error: template file missing, default template HTML will be used')
                themeHTML = DEFAULT_THEME_HTML

        return themeHTML

    def getTitle(self):
        pageObj = self.pageObj
        attr = self.attribute(pageObj)
        return '' if not attr.get('title') else attr['title']

    def getSiteName(self):
        attr = self.attributes(self.obj)
        if attr.get('name'):
            siteName = attr['name']
        else:
            siteName = self.environ['SERVER_NAME']
        return siteName

    def getSiteBasePath(self):
        attr = self.attributes(self.obj)
        if attr.get('base_path'):
            basePath = attr['base_path']
        else:
            basePath = None
        return basePath

    def getThemePath(self, themeObj = None):
        if not themeObj:
            themeObj = self.themeObj
        attr = self.attributes(themeObj)
        if attr.get('dir'):
            dir_attr = attr['dir']
            if dir_attr[-1] != '/':
                dir_attr += '/'
        else:
            dir_attr = ''
        if self.basePath:
            fullPath = '/' + self.basePath + '/' + THEMES_DIR + dir_attr
        else:
            fullPath = '/' + THEMES_DIR + dir_attr
        return fullPath

    def replaceMacroCommands(self, HTML):
        macroCommands = [
            '<%THEME_PATH%>',
            '<%SITENAME%>',
            '<%TITLE%>',
            '<%META%>',
            '<%NAVI%>'
        ]
        replacement = [
            self.getThemePath,
            self.getSiteName,
            self.getTitle,
            self.getMetaHTML,
            self.getNavi
        ]

        edits = zip(macroCommands, replacement)
        for search, replace in edits:
            HTML = HTML.replace(search, replace())
        return HTML

def app(environ, start_response):
    session = environ['beaker.session']

    sitexml = SiteXML(environ)

    status = '200 OK'
    sitexml.response_headers = [
        ('Content-Type', 'text/html; charset=utf-8'),
    ]

    method = environ['REQUEST_METHOD']
    if method == 'POST':
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except ValueError:
            request_body_size = 0

        request_body = environ['wsgi.input'].read(request_body_size)
        d = parse_qs(request_body)

        if 'sitexml' in d:
            if sitexml.saveXML(d.get('sitexml')):
                sitexml.response_body = 'siteXML saved'
            else:
                sitexml.response_body = sitexml.error('siteXML was not saved')
        elif ('cid' in d) and ('content' in d):
            sitexml.saveContent(d.get('cid'), d.get('content'))
        elif (not d.get('username')) and (not d.get('password')):
            sitexml.response_body = sitexml.login(d['username'], d['password'], d.get('edit'))

    elif method == 'GET':
        d = parse_qs(environ['QUERY_STRING'])

        if 'logout' in d:
            sitexml.logout()

        if 'edit' in d:
            if not d.get('username'):
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
        elif not d.get('cid'):
            sitexml.response_body = sitexml.getContent(d.get('cid'))
        elif (not d.get('id')) and (not d.get('name')):
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
