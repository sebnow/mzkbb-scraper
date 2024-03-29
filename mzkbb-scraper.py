#!/usr/bin/env python2
# coding=utf8
from BeautifulSoup import BeautifulSoup, SoupStrainer
from htmlentitydefs import name2codepoint
from urllib2 import urlopen
from urlparse import urljoin, urlparse, urlunparse
import argparse
import cgi
import codecs
import logging
import os
import re
import xml.etree.ElementTree

MZKBB_URL = "http://www.mzkb-b.internetdsl.pl"
MZKBB_LOCATION_URL = "http://www.mzkb-b.internetdsl.pl/miejscow_r.htm"
MZKBB_ROUTE_URL = "http://mzkb-b.internetdsl.pl/linie_r.htm"
SP_URL = "http://mapa.schedulerpoland.pl/request.php?city={0}&latnul=T&lines=N&search="

log = logging.getLogger()
AGENCY = {
	'id': 'MZKBB',
	'name': u'Miejski Zakład Komunikacyjny w Bielsku-Białej',
	'url': MZKBB_URL,
	'timezone': 'Europe/Warsaw',
	'language': 'pl',
	'telephone': '+48338143511',
}

def unescape(s):
	# There is cgi.escape() but no cgi.unescape()?
	return re.sub('&#(%s);' % '|'.join(name2codepoint), lambda m: unichr(name2codepoint[m.group(1)]), s)

def get_locations(page):
	base_url = MZKBB_URL
	#if hasattr(page, 'geturl'):
	#	url = urlparse(page.geturl)
	#	base_url = urlunparse((url.scheme, url.netloc, '', '', '', ''))

	strainer = SoupStrainer('a', href=re.compile('^m_\d+'))
	els = BeautifulSoup(page, parseOnlyThese=strainer)
	for el in els:
		yield {
			"url": urljoin(base_url, el['href']),
			"name": el('font')[0].contents[0].strip(),
		}

def get_stops(page):
	""" Retrieve basic stop information on the specified *page*.

	The *page* should be a file-like object. If the object has
	a *geturl* attribute, such as those returned by urlopen(), the
	returned url will be used as the base url.

	A list of dictionaries containing stop details will be returned. The
	dictionaries have the following keys:

		url: The absolute URL of the stop. The network location will be
		retrieved from *page.geturl()* if available.

		name: The name of the stop.

		id: The id/code of the stop.

	>>> import StringIO
	>>> page = StringIO.StringIO()
	>>> page.write('<a href="p_272_m.htm" target="main">')
	>>> page.write('<font face="Arial" size="-1" color="#000000">')
	>>> page.write('3 Maja/Dworzec&nbsp;&nbsp;-&nbsp;&nbsp;2/1</font></a>')
	>>> page.seek(0)
	>>> list(get_stops(page))
	[{'url': u'http://www.mzkb-b.internetdsl.pl/p_272_m.htm', 'name': u'3 Maja/Dworzec', 'id': u'272'}]
	"""
	base_url = MZKBB_URL
	#if hasattr(page, 'geturl'):
	#	url = urlparse(page.geturl)
	#	base_url = urlunparse((url.scheme, url.netloc, '', '', '', ''))

	strainer = SoupStrainer('a', href=re.compile('^p_\d+'))
	els = BeautifulSoup(page, parseOnlyThese=strainer)
	strip_stop = re.compile("&nbsp.*")
	for el in els:
		stop = {
			"url": urljoin(base_url, el['href']),
			"name": strip_stop.sub("", el('font')[0].contents[0]),
			"id": el['href'][2:-6],
		}
		yield stop

def extract_city_gps(payload):
	""" Extract GPS coordinates for stops from the specified *xml*
	document.

	>>> import StringIO
	>>> xml = StringIO.StringIO()
	>>> xml.write('<?xml version="1.0" encoding="utf-8"?><markers>')
	>>> xml.write('<marker id="357259" name="3 Maja/Dworzec" display="" ')
	>>> xml.write('lat="49.8279341851486" lng="19.0446281433105" id_user="-1" ')
	>>> xml.write('id_sched="9" id_trans="-1" id_slupka=""></marker></markers>')
	>>> xml.seek(0)
	>>> extract_city_gps(xml)
	{'3 Maja/Dworzec': {'longitude': 19.0446281433105, 'lattitude': 49.8279341851486}}
	"""
	gps = {}
	doc = xml.etree.ElementTree.parse(payload)
	for marker in doc.iterfind('marker'):
		name = unescape(marker.get('name'))
		log.debug("Found marker: " + name)
		if len(marker.get('lat')) == 0 or len(marker.get('lng')) == 0:
			log.warning(u"GPS coordinates for {0} are missing".format(name))
			continue
		lattitude = float(marker.get('lat'))
		longitude = float(marker.get('lng'))
		gps[name] = {
			'longitude': longitude,
			'lattitude': lattitude,
		}
	return gps

def extract_routes(payload, agency):
	""" Extract route information from the specified *page*.

	>>> import StringIO
	>>> page = StringIO.StringIO()
	>>> page.write('<table border="0" width="100%" bgcolor="#FFFFFF"')
	>>> page.write('bordercolor="#FFFFFF"><tbody><tr>')
	>>> page.write('<td width="10%" align="center" bgcolor="#FFFFFF"></td>')
	>>> page.write('<td width="10%" align="center" bgcolor="#FFFFC0">')
	>>> page.write('<font face="Arial" size="-1" color="#000000">01</font>')
	>>> page.write('</td><td width="35%" align="center" bgcolor="#FFFFC0">')
	>>> page.write('<a href="linia_t_0.htm" target="main">')
	>>> page.write('<font face="Arial" size="-1" color="#000000">Osiedle ')
	>>> page.write('Beskidzkie</font></a></td>')
	>>> page.write('<td width="35%" align="center" bgcolor="#FFFFC0">')
	>>> page.write('<a href="linia_p_0.htm" target="main"><font face="Arial" ')
	>>> page.write('size="-1" color="#000000">Cygański Las</font></a>')
	>>> page.write('</td><td width="10%" align="center" bgcolor="#FFFFFF">')
	>>> page.write('</td></tr></tbody></table>')
	>>> page.seek(0)
	>>> list(extract_routes(page, {'id': 1}))
	[{'short_name': u'01', 'id': u'01', 'agency_id': 1}]
	"""
	strainer = SoupStrainer('tr')
	soup = BeautifulSoup(payload, parseOnlyThese=strainer)
	for tr in soup:
		tds = tr.findAll('td')
		if len(tds) != 5:
			continue
		short_name = tds[1].findAll('font')[0].string.strip()
		log.debug("Found route: " + short_name)
		yield {'id': short_name, 'agency_id': agency['id'], 'short_name': short_name}

def scrape_city_gps(city):
	xml = urlopen(SP_URL.format("bielskobiala"))
	return extract_city_gps(xml)

def scrape_stops(gps):
	locations = get_locations(urlopen(MZKBB_LOCATION_URL))
	for location in locations:
		log.info("Retrieving stops for " + location['name'])
		location_page = urlopen(location['url'])
		for stop in get_stops(location_page):
			if not stop['name'] in gps:
				# TODO: Get GPS info somehow
				continue
			log.info("Retrieved stop " + stop['name'])
			stop['longitude'] = gps[stop['name']]['longitude']
			stop['lattitude'] = gps[stop['name']]['lattitude']
			yield stop

def scrape_routes(agency):
	page = urlopen(MZKBB_ROUTE_URL)
	return extract_routes(page, agency)

def command_stops(args):
	log.info("Retrieving GPS coordinates for stops in Bielsko Biala")
	gps = scrape_city_gps("bielskobiala")

	log.info("Writing stops.txt")
	fields = ['id', 'name', 'name', 'description', 'lattitude', 'longitude', 'zone_id', 'url']
	for stop in scrape_stops(gps):
		args.file.write(','.join([unicode(k in stop and stop[k] or '') for k in fields]) + u'\n')

def command_routes(args):
	fields = ['route_id', 'agency_id', 'short_name', 'long_name', 'desc', 'type', 'url']
	for route in scrape_routes(AGENCY):
		args.file.write(','.join([unicode(k in route and route[k] or '') for k in fields]) + u'\n')

def command_agencies(args):
	fields = ['id', 'name', 'url', 'timezone', 'language', 'telephone', 'fare_url']
	for agency in [AGENCY]:
		args.file.write(','.join([unicode(k in agency and agency[k] or '') for k in fields]) + u'\n')

if __name__ == "__main__":
	args_main = argparse.ArgumentParser(description='MZK Bielsko Biala scraper')
	args_main.add_argument('-v', '--verbose', help='increase verbosity',
		action='count', dest='verbosity')
	args_main.set_defaults(verbosity=0)
	sub_args = args_main.add_subparsers(help='command help')

	args_common = argparse.ArgumentParser(add_help=False)
	args_common.add_argument('-f', '--file', help='write to FILE',
		type=argparse.FileType('w'), default='-')

	args_agencies = sub_args.add_parser('agencies', help='scrape agency information',
		parents=[args_common])
	args_agencies.set_defaults(func=command_agencies)

	args_stops = sub_args.add_parser('stops', help='scrape stop information',
		parents=[args_common])
	args_stops.set_defaults(func=command_stops)

	args_routes = sub_args.add_parser('routes', help='scrape route information',
		parents=[args_common])
	args_routes.set_defaults(func=command_routes)

	args = args_main.parse_args()

	# Set logging level
	logging_level = min(logging.WARNING - (args.verbosity * logging.DEBUG), logging.WARNING)
	if logging_level < logging.DEBUG:
		logging_level = logging.DEBUG
	logging.basicConfig(level=logging_level)

	args.func(args)

