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

        self.status = '200 OK'
        self._response_headers = {}
        self._response_body = ''

        self.editMode = False

        self.setEditMode()
        self.obj = self.getObj()
        self.pid = self.getPid()
        self.pageObj = self.getPageObj(self.pid)
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
        for k, v in pageObj.items():
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
        for k, v in parent.items():
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
        for k, v in self.obj.items():
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
            if dir_attr != '':  # meaningless
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
        attr = self.attributes(pageObj)
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

    def getThemePath(self, themeObj=None):
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

    def getMetaHTML(self, pageObj=None):
        if not pageObj:
            pageObj = self.pageObj
        metaHTML = ''
        for k, v in self.obj.items():
            if k.lower() == 'meta':
                metaHTML += self.singleMetaHTML(v)
        for k, v in pageObj.items():
            if k.lower() == 'meta':
                metaHTML += self.singleMetaHTML(v)
        return metaHTML

    def singleMetaHTML(self, metaObj):
        attr = self.attributes(metaObj)
        metaHTML = '<meta'
        if attr:
            for k, v in attr.items():
                metaHTML += ' ' + k + '="' + v + '"'
        metaHTML += '>'
        return metaHTML

    def replaceThemeContent(self, HTML):
        return self.replaceContent(HTML, 'theme')

    def replacePageContent(self, HTML):
        return self.replaceContent(HTML, 'page')

    def replaceContent(self, HTML, where):
        if where == 'page':
            obj = self.pageObj
        elif where == 'theme':
            obj = self.themeObj
        else:
            return None
        if obj:
            for k, v in obj.items():
                if k.lower() == 'content':
                    attr = self.attributes(v)
                    name = attr['name']
                    search = '<%CONTENT(' + name + ')%>'
                    if HTML.find(search) != -1:
                        if attr.get('type') == 'module':
                            file = MODULES_DIR + v
                            if os.path.isfile(file):
                                with open(file, 'r') as f:
                                    contents = f.read()  # evaluate???
                            else:
                                self.error('Error: module file ' + attr['file'] + ' does not exist')
                    else:
                        file = CONTENT_DIR + v
                        if os.path.isfile(file):
                            with open(file, 'r') as f:
                                contents = f.read()
                            contents = '<div class="siteXML-content" cid="' + attr[
                                'id'] + '" cname="' + name + '">' + contents + '</div>'
                        else:
                            self.error('Error: content file ' + attr['file'] + ' does not exist')
                    HTML = HTML.replace(search, contents)
        return HTML

    def getNavi(self, obj=None, maxlevel=0, level=0):
        level += level
        if not obj:
            obj = self.obj
        HTML = ''
        if maxlevel == 0 or maxlevel >= level:
            for k, v in obj:
                if k.lower() == 'page':
                    attr = self.attributes(v)
                    if attr.get('nonavi'):
                        if attr.get('nonavi').lower() == 'yes':
                            continue
                    liClass = ' class="siteXML-current"' if attr['id'] == self.pid else ''
                    href = '/' + attr['alias'] if attr.get['alias'] else '/?id=' + attr['id']
                    if self.basePath:
                        href = '/' + self.basePath + href

                    hasContent = False
                    for i in v:
                        if i.lower() == 'content':
                            hasContent = True
                            break
                    if hasContent:
                        HTML += '<li' + liClass + ' pid="' + attr['id'] + '"><a href="' + href + '" pid="' + attr[
                            'id'] + '">' + attr['name'] + '</a>'
                    else:
                        HTML += '<li' + liClass + 'pid="' + attr['id'] + '">' + attr['name'] + ''
                    HTML += self.getNavi(v, maxlevel, level)
                    HTML += '</li>'
            if HTML != '':
                HTML = '<ul class=\"siteXML-navi level-$level\">' + HTML + '</ul>'
        return HTML

    def replaceNavi(self, HTML):
        HTML = HTML.replace('<%NAVI%>', self.getNavi())
        pos = HTML.find('<%NAVI')
        while pos:
            pos1 = HTML.find('(', pos + 1)
            pos2 = HTML.find(')', pos + 1)
            if pos1 and pos2:
                arg = HTML[pos1 + 1:pos2 - pos1 - 1]
                arg = arg.split(',')
            else:
                arg = None
            if arg:
                needle = "<%NAVI(" + arg[0] + "," + arg[1] + ")%>"
                pageObj = self.getPageObj(arg[0])
                replace = self.getNavi(pageObj, arg[0])
                HTML = HTML.replace(needle, replace)
            pos = HTML.find('<%NAVI', pos + 1)
        return HTML

    def replacePlink(self, HTML):
        pos = HTML.find('<%PLINK')
        while pos:
            pos1 = HTML.find('(', pos + 1)
            pos2 = HTML.find(')', pos + 1)
            if pos1 and pos2:
                arg = HTML[pos1 + 1:pos2 - pos1 - 1]
            else:
                arg = None
            if arg:
                needle = "<%PLINK(" + arg + ")%>"
                replace = self.getPlink(arg)
                HTML = HTML.replace(needle, replace)
            pos = HTML.find('<%PLINK', pos + 1)
            return HTML

    def getPlink(self, id):
        pageObj = self.getPageObj(id)
        attr = self.attributes(pageObj)
        if attr.get('alias'):
            href = '/' + attr['alias']
        else:
            href = '/?id=' + id
        pname = attr['name']
        html = '<a href="' + href + '" plink="' + id + '" pid="' + id + '">' + pname + '</a>'
        return html

    def appendScripts(self, HTML):
        pos = HTML.lower().find('</body>')
        scripts = '<!--<script src="' + (
            self.basePath + '/' if self.basePath else '') + '/js/jquery-2.1.3.min.js"></script>-->' + '<script src="' + (
                      self.basePath + '/' if self.basePath else '') + '/js/sitexml.js"></script>' + AJAX_BROWSING_SCRIPT + (
                      CONTENT_EDIT_SCRIPT if self.editMode else '')
        if pos:
            HTML = HTML[:pos] + scripts + HTML[pos:]
        else:
            HTML = scripts
        return HTML

    def page(self):
        pageHTML = self.getThemeHTML(self.themeObj)
        pageHTML = self.replaceNavi(pageHTML)
        pageHTML = self.replacePageContent(pageHTML)
        pageHTML = self.replaceThemeContent(pageHTML)
        pageHTML = self.replaceMacroCommands(pageHTML)
        pageHTML = self.replacePlink(pageHTML)
        pageHTML = self.appendScripts(pageHTML)
        return pageHTML

    "@param {String} $error"
    def error(self, error):
        if DEBUG:
            self.response_body = error + '\n'

    "@param {SimpleXML Object} $obj"
    def attributes(self, obj):
        if not obj:
            return None
        attr = obj.attrib
        newattr = {}
        for k, v in attr:
            newattr[k.lower()] = v
        return newattr

    def getXML(self):
        with open(SITEXML, 'r') as f:
            return f.read()

    def saveXML(self, xmlstr):
        with open(SITEXML, 'w') as f:
            return f.write(xmlstr)

    def saveContent(self, cid, content):
        file = self.obj.findall("//content[@id='" + cid + "']")
        file = CONTENT_DIR + file[0]
        if os.path.isfile(file):
            try:
                with open(file, 'w') as f:
                    f.write(content)
                self.response_body = 'Content saved'
            except:
                self.response_headers = '500 Server Error'
                self.error('Error: Content not saved: ' + file)
        else:
            self.response_headers = '404 Not Found'
            self.error('Error: Content file ' + file + ' does not exist')

    def getContentByIdAndName(self, id, name):
        c = self.obj.findall("//page[@id='" + id + "']/content[@name='" + name + "']")
        attr = self.attributes(c[0])
        cid = attr['id']
        return self.getContent(cid, c)

    """
    @param {Integer | String} $cid - content id
    @param {XML Object} $cobj - not required; content node object
    """
    def getContent(self, cid, cobj = None):
        if not cobj:
            file = self.obj.findall("//content[@id='" + cid + "']")
        else:
            file = cobj

        file = CONTENT_DIR + file[0]
        if os.path.isfile(file):
            with open(file, 'r') as f:
                content = f.read()
            content = self.replacePlink(content)
        else:
            content = None
        return content


def app(environ, start_response):
    session = environ['beaker.session']

    sitexml = SiteXML(environ)

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
        sitexml.status = '405 Method Not Allowed'
        sitexml.response_headers = [
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Allow', 'GET, POST'),
        ]

    start_response(sitexml.status, sitexml.response_headers)
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
