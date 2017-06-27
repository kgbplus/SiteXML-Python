![SiteXML logo](http://sitexml.info/.themes/byYaroslav/images/logo_index.png)
# SiteXML:Python  
WSGI application SiteXML engine. Read more about SiteXML[http://sitexml.info/](http://sitexml.info/)

### USAGE:

Choose one of the following:

1. Start `sitexml.py` by itself (install requirements first)
2. Use `gunicorn` webserver: `gunicorn sitexml:wsgi_app`
3. Apache webserver with wsgi_mod. [Read configuration guide here](http://modwsgi.readthedocs.io/en/develop/user-guides/quick-configuration-guide.html)

* [Example of configruation](http://flask.pocoo.org/docs/0.12/deploying/mod_wsgi/)

(Put
``` from sitexml import wsgi_app as application ```
into your `myapp.wsgi` file.)

### NOTES:

- The minimum requirement is the presence of .site.xml file in the site root.
- About PEP8 coding convention violation (camelCase method's names): this violation was left consciously to make comparison with SiteXML:PHP easy.
