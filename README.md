![SiteXML logo](http://sitexml.info/.themes/byYaroslav/images/logo_index.png)
# SiteXML:Python  
WSGI application SiteXML engine. Read more about SiteXML[http://sitexml.info/](http://sitexml.info/)

### USAGE:

Choose one of the following:

1. Start `sitexml.py` by itself (install requirements first)
2. Use `gunicorn` webserver: `gunicorn sitexml:wsgi_app`
3. Apache webserver with wsgi_mod. [Read configuration guide here](http://modwsgi.readthedocs.io/en/develop/user-guides/quick-configuration-guide.html)

* [Example of configruation](https://github.com/kgbplus/SiteXML-Python/blob/master/sitexml-apache2.conf)
Correct pathes and include this file into your apache2.conf (or httpd.conf depending of Apache preferencies).
Unfortunately, You have to make aliases for all static files and directories.

### NOTES:

- The minimum requirement is the presence of `.site.xml` file in the site root.
- About PEP8 coding convention violation (camelCase method's names): this violation was left consciously to make comparison with `SiteXML:PHP` easy.
