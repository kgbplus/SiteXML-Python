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
from urllib.parse import parse_qsl, unquote_plus
import lxml.etree as ET
from beaker.middleware import SessionMiddleware
import static


REAL_PATH = '/var/www/html/'
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


def xml_pairs(root):
    "suppliemental function - replacement of php's foreach ($obj as $k => $v)"
    for child in root.iterchildren():
        yield child.tag, child


class SiteXML:
    def __init__(self, environ):

        self.environ = environ
        self.session = environ['beaker.session']

        self.status = '200 OK'
        self._response_headers = []
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
        self._response_headers.append(header)

    @property
    def response_body(self):
        return self._response_body

    @response_body.setter
    def response_body(self, content):
        self._response_body += content

    def setEditMode(self):
        if ('edit' in self.session) and ('username' in self.session):
            self.response_headers = ('Cache-Control', 'no-cache, must-revalidate')
            self.editMode = True

    def loginScreen(self, edit=''):
        return ('''
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
    <form action="/''' + (self.basePath if self.basePath is not None else '') + '''" method="post">
        <div>
            <input placeholder="Username" name="username" type="text" autofocus="true">
        </div>
        <div>
            <input placeholder="Password" name="password" type="password">
        </div>
        <div>
        ''' + ('<input type="hidden" name="edit" value="true">' if edit == 'edit' else '') + '''
        <input type="submit">
        </div>
    </form>
</div>
</body>
</html>
        ''')

    def login(self, username, password, edit):
        m = hashlib.md5()
        m.update(password.encode())
        password = m.hexdigest()

        user = self.getUser(username)
        if user:
            if user[1] == password:
                self.session['username'] = username
                if edit:
                    self.session['edit'] = True
                self.status = '302 Found'
                self.response_headers = ('location', '/' + (self.basePath if self.basePath is not None else ''))

    @staticmethod
    def getUser(username):
        if os.path.isfile(REAL_PATH + USERS_FILE):
            with open(REAL_PATH + USERS_FILE, 'r', encoding='utf-8') as f:
                for user in f:
                    user = user.split(':')
                    if user[0] == username:
                        user[1] = user[1].replace('\n', '')
                        return user

    def logout(self):
        self.session.delete()

    @staticmethod
    def getObj():
        if os.path.isfile(REAL_PATH + SITEXML):
            return ET.parse(REAL_PATH + SITEXML).getroot()
        else:
            raise FileNotFoundError

    def getPid(self):
        pid = None
        d = dict(parse_qsl(self.environ['QUERY_STRING']))
        if d == {}:
            d = dict.fromkeys(self.environ['QUERY_STRING'].split('&'))

        if self.environ['PATH_INFO'] == '': # mod_wsgi return empty PATH_INFO if in root
            self.environ['PATH_INFO'] = '/'

        if d.get('id') is not None:
            pid = d['id']
        elif self.environ['PATH_INFO'] != '/':
            if self.environ['PATH_INFO'][0] == '/':
                alias = self.environ['PATH_INFO'][1:]
            else:
                alias = self.environ['PATH_INFO']

            alias = unquote_plus(alias)
            aliasNoEndingSlash = alias.rstrip('/')
            pid = self.getPageIdByAlias(aliasNoEndingSlash)

        if pid is None:
            defaultPid = self.getDefaultPid()
            if defaultPid is None:
                defaultPid = self.getFirstPagePid()
            pid = defaultPid

        if pid is None:
            raise RuntimeError('Fatal error: no pages in this site')
        else:
            return pid

    def getDefaultPid(self, pageObj=None):
        "recursive"
        if pageObj is None:
            pageObj = self.obj
        defaultPid = None
        for k, v in xml_pairs(pageObj):
            if k.lower() == 'page':
                attr = self.attributes(v)
                if attr.get('startpage') == 'yes':
                    defaultPid = attr.get('id')
                    break
                else:
                    defaultPid = self.getDefaultPid(v)
                    if defaultPid is not None:
                        break
        return defaultPid

    def getPageIdByAlias(self, alias, parent=None):
        " @ param {String} $alias - make sure that it doesn't end with slash - ' / ' "
        pid = None
        if parent is None:
            parent = self.obj
        for k, v in xml_pairs(parent):
            if k.lower() == 'page':
                attr = self.attributes(v)
                if attr.get('alias') and attr.get('alias').rstrip() == alias:
                    pid = attr.get('id')
                else:
                    pid = self.getPageIdByAlias(alias, v)
                if pid:
                    break
        return pid

    def getFirstPagePid(self):
        pid = None
        for k, v in xml_pairs(self.obj):
            if k.lower() == 'page':
                attr = self.attributes(v)
                pid = attr.get('id')
                break
        return pid

    def getPageObj(self, pid):
        if pid is not None:
            pageObj = self.obj.xpath(".//page[@id='" + str(pid) + "']")
        else:
            pageObj = self.obj.xpath(".//page")
        if pageObj is not None:
            return pageObj[0]
        else:
            return None

    def getTheme(self, pageObj=None):
        """
         param {Object} page object.If not given, $this->pageObj will be used
         returns {Object} theme by page object
        """
        if pageObj is None:
            pageObj = self.pageObj
        attr = self.attributes(pageObj)
        themeId = attr.get('theme')
        if themeId is not None:
            themeObj = self.obj.xpath(".//theme[@id='" + themeId + "']")
            if themeObj is None:
                self.error("Error: theme with id " + themeId + "does not exist")
        else:
            themeObj = self.obj.xpath(
                ".//theme[contains(translate(@default, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'yes')]")
            if themeObj is None:
                themeObj = self.obj.xpath(".//theme")
        if themeObj is not None and len(themeObj) > 0:
            return themeObj[0]
        else:
            return None

    def getThemeHTML(self, themeObj=None):
        """
        @param {Object} theme || If not given, DEFAULT_THEME_HTML will be returned
        @returns {String} theme html
        """
        if themeObj is None:
            self.error('SiteXML error: template does not exist, default template HTML will be used')
            themeHTML = DEFAULT_THEME_HTML
        else:
            attr = self.attributes(themeObj)
            dir_attr = '' if 'dir' not in attr else attr['dir']
            path = THEMES_DIR
            if path[-1] != '/':
                path += '/'
            if dir_attr != '':  # meaningless
                path += dir_attr
            if path[-1] != '/':
                path += '/'
            if 'file' in attr:
                path += attr['file']
                if os.path.isfile(REAL_PATH + path):
                    with open(REAL_PATH + path, 'r', encoding='utf-8') as f:
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
        return '' if 'title' not in attr else attr['title']

    def getSiteName(self):
        attr = self.attributes(self.obj)
        if 'name' in attr:
            siteName = attr['name']
        else:
            siteName = self.environ['SERVER_NAME']
        return siteName

    def getSiteBasePath(self):
        attr = self.attributes(self.obj)
        if 'base_path' in attr:
            basePath = attr['base_path']
        else:
            basePath = None
        return basePath

    def getThemePath(self, themeObj=None):
        if themeObj is None:
            themeObj = self.themeObj
        attr = self.attributes(themeObj)
        if 'dir' in attr:
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
        if pageObj is None:
            pageObj = self.pageObj
        metaHTML = ''
        for k, v in xml_pairs(self.obj):
            if k.lower() == 'meta':
                metaHTML += self.singleMetaHTML(v)
        for k, v in xml_pairs(pageObj):
            if k.lower() == 'meta':
                metaHTML += self.singleMetaHTML(v)
        return metaHTML

    def singleMetaHTML(self, metaObj):
        attr = self.attributes(metaObj)
        metaHTML = '<meta'
        if len(attr):
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
        if obj is not None:
            for k, v in xml_pairs(obj):
                if k.lower() == 'content':
                    contents = ''
                    attr = self.attributes(v)
                    name = attr.get('name')
                    search = '<%CONTENT(' + name + ')%>'
                    if HTML.find(search) != -1:
                        if attr.get('type') == 'module':
                            file = MODULES_DIR + v.text
                            if os.path.isfile(REAL_PATH + file):
                                with open(REAL_PATH + file, 'r', encoding='utf-8') as f:
                                    contents = f.read()  # evaluate???
                            else:
                                self.error('Error: module file ' + file + ' does not exist')
                        else:
                            file = CONTENT_DIR + v.text
                            if os.path.isfile(REAL_PATH + file):
                                with open(REAL_PATH + file, 'r', encoding='utf-8') as f:
                                    contents = f.read()
                                contents = '<div class="siteXML-content" cid="' + attr[
                                    'id'] + '" cname="' + name + '">' + contents + '</div>'
                            else:
                                self.error('Error: content file ' + file + ' does not exist')
                        HTML = HTML.replace(search, contents)
        return HTML

    def getNavi(self, obj=None, maxlevel=0, level=0):
        level += level
        if obj is None:
            obj = self.obj
        HTML = ''
        if maxlevel == 0 or maxlevel >= level:
            for k, v in xml_pairs(obj):
                if k.lower() == 'page':
                    attr = self.attributes(v)
                    if 'nonavi' in attr:
                        if attr.get('nonavi').lower() == 'yes':
                            continue
                    liClass = ' class="siteXML-current"' if attr.get('id') == self.pid else ''
                    href = '/' + attr['alias'] if 'alias' in attr else '/?id=' + attr.get('id')
                    if self.basePath is not None:
                        href = '/' + self.basePath + href

                    hasContent = False
                    for i in v.iterchildren():
                        if i.tag.lower() == 'content':
                            hasContent = True
                            break
                    if hasContent:
                        HTML += '<li' + liClass + ' pid="' + attr.get(
                            'id') + '"><a href="' + href + '" pid="' + attr.get('id') + '">' + attr['name'] + '</a>'
                    else:
                        HTML += '<li' + liClass + 'pid="' + attr.get('id') + '">' + attr.get('name') + ''
                    HTML += self.getNavi(v, maxlevel, level)
                    HTML += '</li>'
            if HTML != '':
                HTML = '<ul class=\"siteXML-navi level-' + str(level) + '\">' + HTML + '</ul>'
        return HTML

    def replaceNavi(self, HTML):
        HTML = HTML.replace('<%NAVI%>', self.getNavi())
        pos = HTML.find('<%NAVI')
        while pos >= 0:
            pos1 = HTML.find('(', pos + 1)
            pos2 = HTML.find(')', pos + 1)
            if pos1 >= 0 and pos2 >= 0:
                arg = HTML[pos1 + 1:pos2 - pos1 - 1]
                arg = arg.split(',')
            else:
                arg = None
            if arg is not None:
                needle = "<%NAVI(" + arg[0] + "," + arg[1] + ")%>"
                pageObj = self.getPageObj(arg[0])
                replace = self.getNavi(pageObj, arg[0])
                HTML = HTML.replace(needle, replace)
            pos = HTML.find('<%NAVI', pos + 1)
        return HTML

    def replacePlink(self, HTML):
        pos = HTML.find('<%PLINK')
        while pos >= 0:
            pos1 = HTML.find('(', pos + 1)
            pos2 = HTML.find(')', pos + 1)
            if pos1 >= 0 and pos2 >= 0:
                arg = HTML[pos1+1:pos2]
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
        if 'alias' in attr:
            href = '/' + attr['alias']
        else:
            href = '/?id=' + id
        pname = attr.get('name')
        html = '<a href="' + href + '" plink="' + id + '" pid="' + id + '">' + pname + '</a>'
        return html

    def appendScripts(self, HTML):
        pos = HTML.lower().find('</body>')
        scripts = '<!--<script src="' + (
            self.basePath + '/' if self.basePath else '') + '/js/jquery-2.1.3.min.js"></script>-->' + '<script src="' + (
                      self.basePath + '/' if self.basePath else '') + '/js/sitexml.js"></script>' + AJAX_BROWSING_SCRIPT + (
                      CONTENT_EDIT_SCRIPT if self.editMode else '')
        if pos >= 0:
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

    def error(self, error):
        "@param {String} $error"
        if DEBUG:
            self.response_body = error + '\n'

    def attributes(self, obj):
        "@param {SimpleXML Object} $obj"
        if obj is None:
            return {}
        attr = obj.items()
        newattr = {}
        for k, v in attr:
            newattr[k.lower()] = v
        return newattr

    def getXML(self):
        with open(REAL_PATH + SITEXML, 'r', encoding='utf-8') as f:
            return f.read()

    def saveXML(self, xmlstr):
        with open(REAL_PATH + SITEXML, 'w', encoding='utf-8') as f:
            return f.write(xmlstr)

    def saveContent(self, cid, content):
        file = self.obj.xpath(".//content[@id='" + str(cid) + "']")
        file = CONTENT_DIR + file[0].text
        if os.path.isfile(REAL_PATH + file):
            try:
                with open(REAL_PATH + file, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.response_body = 'Content saved'
            except:
                self.status = '500 Server Error'
                self.error('Error: Content not saved: ' + file)
        else:
            self.status = '404 Not Found'
            self.error('Error: Content file ' + file + ' does not exist')

    def getContentByIdAndName(self, id, name):
        c = self.obj.xpath(".//page[@id='" + str(id) + "']/content[@name='" + str(name) + "']")
        attr = self.attributes(c[0])
        cid = attr.get('id')
        return self.getContent(cid, c)

    def getContent(self, cid, cobj=None):
        """
        @param {Integer | String} $cid - content id
        @param {XML Object} $cobj - not required; content node object
        """
        if cobj is None:
            file = self.obj.xpath(".//content[@id='" + str(cid) + "']")
        else:
            file = cobj

        file = CONTENT_DIR + file[0].text
        if os.path.isfile(REAL_PATH + file):
            with open(REAL_PATH + file, 'r', encoding='utf-8') as f:
                content = f.read()
            content = self.replacePlink(content)
        else:
            content = None
        return content


def app(environ, start_response):
    session = environ['beaker.session']

    sitexml = SiteXML(environ)

    sitexml.response_headers = ('Content-Type', 'text/html; charset=utf-8')

    method = environ['REQUEST_METHOD']
    if method == 'POST':
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except ValueError:
            request_body_size = 0

        request_body = environ['wsgi.input'].read(request_body_size)
        d = dict(parse_qsl(request_body.decode()))

        if d.get('sitexml') is not None:
            if session.get('username') is None:
                sitexml.status = 'HTTP/1.1 401 Access denied'
            elif sitexml.saveXML(d.get('sitexml')):
                sitexml.response_body = 'siteXML saved'
            else:
                sitexml.response_body = sitexml.error('siteXML was not saved')
        elif (d.get('cid') is not None) and (d.get('content') is not None):
            if session.get('username') is None:
                sitexml.status = 'HTTP/1.1 401 Access denied'
            else:
                sitexml.saveContent(d.get('cid'), d.get('content'))
        elif d.get('username') is not None and d.get('password') is not None:
            sitexml.login(d['username'], d['password'], d.get('edit'))

    elif method == 'GET':
        d = dict(parse_qsl(environ['QUERY_STRING']))
        if d == {}:
            d = dict.fromkeys(environ['QUERY_STRING'].split('&'))

        if 'logout' in d:
            sitexml.logout()

        if 'edit' in d:
            if 'username' in d:
                session['edit'] = True
                sitexml.response_body = sitexml.page()
            else:
                sitexml.response_body = sitexml.loginScreen('edit')
        elif 'sitexml' in d:
            sitexml.response_headers = ('Content-Type', 'text/xml; charset=utf-8')
            sitexml.response_body = sitexml.getXML()
        elif 'login' in d:
            sitexml.response_body = sitexml.loginScreen()
        elif d.get('cid') is not None:
            sitexml.response_body = sitexml.getContent(d.get('cid'))
        elif (d.get('id') is not None) and (d.get('name') is not None):
            sitexml.response_body = sitexml.getContentByIdAndName(d.get('id'), d.get('name'))
        else:
            sitexml.response_body = sitexml.page()

    else:
        sitexml.status = '405 Method Not Allowed'
        sitexml.response_headers = ('Content-Type', 'text/html; charset=utf-8')
        sitexml.response_headers = ('Allow', 'GET, POST')

    start_response(sitexml.status, sitexml.response_headers)
    return [sitexml.response_body.encode()]


session_opts = {
    'session.auto': True,
    'session.type': 'cookie',
    'session.validate_key': 'ABCDEF',
    'session.cookie_expires': True,
    'session.httponly': True,
    'session.secure': True
}

session_app = SessionMiddleware(app, session_opts)
wsgi_app = static.Cling(REAL_PATH, not_found=session_app, method_not_allowed=session_app)
application = session_app

if __name__ == '__main__':
    try:
        from wsgiref.simple_server import make_server

        httpd = make_server('', 8080, wsgi_app)
        print('Serving on port 8080...')
        httpd.serve_forever()

    except KeyboardInterrupt:
        print('Goodbye.')
