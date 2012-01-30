#!/usr/bin/env python2
# coding=utf8
from BeautifulSoup import BeautifulSoup, SoupStrainer
from urllib2 import urlopen
from urlparse import urljoin, urlparse, urlunparse
import cgi
import csv
import logging
import re

MZKBB_URL = "http://www.mzkb-b.internetdsl.pl"
MZKBB_LOCATION_URL = "http://www.mzkb-b.internetdsl.pl/miejscow_r.htm"
LB_URL = "http://dev.lubie.bielsko.pl"

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

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

def extract_city_gps(page):
	""" Extract GPS coordinates for stops on the specified *page*.

	>>> import StringIO
	>>> page = StringIO.StringIO()
	>>> page.write('<a href="#" onclick="javascript:mapa.setCenter(')
	>>> page.write('new google.maps.LatLng(49.827934,19.044628));')
	>>> page.write('mapa.setZoom(15); return false;">')
	>>> page.write('<strong>3 Maja/Dworzec</strong></a>')
	>>> page.seek(0)
	>>> extract_city_gps(page)
	{u'3 Maja/Dworzec': {'longitude': 19.044628, 'lattitude': 49.827934}}
	"""
	strainer = SoupStrainer('a', onclick=re.compile('maps\.LatLng'))
	soup = BeautifulSoup(page, parseOnlyThese=strainer)
	log.debug(soup.prettify())
	onclick_re = re.compile('LatLng\((\d+(?:.\d*))?,(\d+(?:.\d*)?)\)')
	gps = {}
	for anchor in soup:
		'onclick' in anchor or next
		name = anchor.findAll('strong')[0].string.strip()
		log.debug("Found stop: " + name)
		match = onclick_re.search(anchor['onclick'])
		lattitude = float(match.groups()[0])
		longitude = float(match.groups()[1])
		gps[name] = {
			'longitude': longitude,
			'lattitude': lattitude,
		}
	return gps

def scrape_stops():
	locations = get_locations(urlopen(MZKBB_LOCATION_URL))
	log.debug("Locations: " + repr(locations))
	for location in locations:
		location_page = urlopen(location['url'])
		for stop in get_stops(location_page):
			stop['name'] in gps or next # TODO: Get GPS info somehow
			stop['longitude'] = gps[stop['name']]['longitude']
			stop['lattitude'] = gps[stop['name']]['lattitude']
			yield stop


if __name__ == "__main__":
	log.info("Retrieving GPS coordinates for stops in Bielsko Biala")
	gps = scrape_city_gps("bielskobiala")
	with open("stops.txt", "wb") as fh:
		log.info("Writing stops.txt")
		stops_csv = csv.DictWriter(fh, ['id', 'name', 'name', 'description', 'lattitude', 'longitude', 'zone_id', 'url'])
		[stops_csv.writerow(s) for s in scrape_stops(gps)]

