#!/usr/bin/python

# File: solr_update_proxy.py
# Description: Rewrites Solr updates to add semantic tags
# Created: 2010-11-12
# Author: Neil Harris

import cgitb, cgi, sys, urllib, urllib2, string, re, os, time, traceback

def urlquote(x):
    return urllib.quote_plus(x)

def make_url_fields(key, values):
    return string.join(["%s=%s" % (urlquote(key), urlquote(val)) for val in values], "&")

def is_bad_request():
    if os.environ.get("REQUEST_METHOD", None) != "POST": return "not a POST command"
    if not os.environ.get("HTTP_HOST", None): return "no HTTP_HOST specified"
    return 0

# Mangles a URI into something that can be a valid facet name
def mangle_uri(uri):
    ok_chars = string.uppercase + string.lowercase + string.digits
    ok_dict = dict(zip(ok_chars, ok_chars))
    return "mu_" + string.join([ok_dict.get(x, "_") for x in uri], '')

# Process a single XML segment
def rewrite_stanza(text):
    if text[:5] != "<doc>":
        return text
    row_uri = re.findall(r'<field name="ss_cck_field_cat_rowuri">(.*?)</field>', text)
    if not row_uri:
       return text
    row_uri = row_uri[0]
    # And make some sample metadata fields
    return string.replace(text, "</doc>", '<field name="foo">foobar</field><field name="%s">%s</field></doc>' % (mangle_uri(row_uri), row_uri))

# Break the input XML down into segments, process, then reassemble
def rewrite_content(text):
   return string.join(map(rewrite_stanza, re.findall(r"(?s)<doc>.*?</doc>|<.*?>|[^<]+", text)), "")

logfile = open("/tmp/solr_update_proxy_log_%0.5f" % time.time(), "w")
print >> logfile, "environment"
for k in os.environ:
    print >> logfile, k, os.environ.get(k)
logfile.flush()

if os.environ.get('HTTPS', '') == 'on':
    # Warning: proxied HTTPS requests will not attempt to validate the server certificate!
    protocol = 'https'
else:
    protocol = 'http'

# Do some sanity checking before actually dispatching: we are not a general-purpose proxy
if is_bad_request():
    print "Status: 403 Forbidden"
    print "Content-type: text/plain"
    print 
    print "I'm sorry Dave, I can't do that:", is_bad_request()

    sys.exit(0)

try:
	# Redirect to call update interface of local installation of Solr search
	absolute_url = '%s://%s:%d/solr/update/' % (protocol, os.environ['HTTP_HOST'], 8983)

	content_type = os.environ['CONTENT_TYPE']
	content_length = os.environ['CONTENT_LENGTH']
	content = sys.stdin.read()

	print >> logfile, "-------- indexing input data:"
	print >> logfile, content
	logfile.flush()

        content = rewrite_content(content)

	print >> logfile, "-------- rewritten input data:"
	print >> logfile, content
	logfile.flush()

	request = urllib2.Request(absolute_url, content, {'Content-Type': content_type})
	urlobject = urllib2.urlopen(request)
	results = urlobject.read()
	results_type = urlobject.info().gettype()
except urllib2.HTTPError, e:
        results = repr((e.code, e.msg, e.headers.items(), e.read()))
        results_type = "text/plain"
except:
        exc_info = sys.exc_info()
        tb = traceback.format_tb(exc_info[2])
	results = "an exception happened: " + absolute_url + " " + repr(exc_info[0]) + "\n" + string.join(tb, "")
	results_type = "text/plain"

print >> logfile, "-------- indexing output data:"
print >> logfile, results
logfile.close()

sys.stdout.write("Content-Type: %s\r\n" % results_type)
sys.stdout.write("Content-Length: %d\r\n\r\n" % len(results))
sys.stdout.write(results)
sys.stdout.flush()
sys.exit(0)
