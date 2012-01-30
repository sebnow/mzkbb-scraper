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

def get_stop_detail_page(name):
	qstring = cgi.escape(name).encode('ascii', 'xmlcharrefreplace').replace(" ", "+")
	url = urljoin(LB_URL, "/m/szukaj?q=" + qstring)
	log.debug("Retrieving GPS details from " + url)
	page = urlopen(url)

	results = BeautifulSoup(page).findAll("ul", attrs={"class": "links"})[0].findAll('a')
	if len(results) == 0:
		log.error("GPS coordinates for " + name + " not available")
		return {'longitude': 0, 'lattitude': 0}

	url = results[0]['href']
	log.debug("Found stop detail page: " + url)
	page = urlopen(url)
	soup = BeautifulSoup(page)
	log.debug(soup.prettify())

	platforms = filter(lambda e: e.string.strip()[:5] == "Peron", soup.findAll('strong'))
	if len(platforms) > 0:
		log.warning("Multiple platforms: " + ', '.join(map(lambda e: e.string.strip(), platforms)))
		url = platforms[0].parent.parent['href']
		log.debug("Found stop detail page: " + url)
		page = urlopen(url)
	
def extract_stop_gps(page):
	""" Extract GPS information from the specified *page*.

	Returns a dictionary with the WGS84 *longitude* and *lattitude*.

	>>> import StringIO
	>>> page = StringIO.StringIO()
	>>> page.write('<div id="peron-info">')
	>>> page.write('''<p>GPS: <strong>49°50'06" N, 19°00'32" E</strong></p>''')
	>>> page.write('</div>')
	>>> page.seek(0)
	>>> extract_stop_gps(page)
	{'longitude': 49.835, 'lattitude': 19.00888888888889}
	"""
	soup = BeautifulSoup(page)
	info = soup.findAll('div', id="peron-info")[0]

	gps = info.findAll('p')[0].findAll('strong')[0].contents[0].strip()
	gps = gps.split(', ', 2)[:2]

	gps_re = re.compile("(\d+).(\d+)'(\d+)\"\s*(\w)")
	[d, m, s, di] = gps_re.match(gps[0]).groups()[:4]
	lon = dms_to_decimal(int(d), int(m), int(s), di)

	[d, m, s, di] = gps_re.match(gps[1]).groups()[:4]
	lat = dms_to_decimal(int(d), int(m), int(s), di)

	return {
		"longitude": lon,
		"lattitude": lat,
	}

def dms_to_decimal(degress, minutes, seconds, direction):
	""" Convert degrees, minutes and seconds into decimal.

	>>> round(dms_to_decimal(49, 50, 06, "E"), 4)
	49.835
	>>> round(dms_to_decimal(19, 0, 32, "N"), 4)
	19.0089
	>>> round(dms_to_decimal(49, 50, 06, "W"), 4)
	-49.835
	>>> round(dms_to_decimal(19, 0, 32, "S"), 4)
	-19.0089
	"""
	direction = direction.upper()
	sign = 1
	if direction == 'W' or direction == 'S':
		sign = -1
	return (degress + (minutes / 60.0) + (seconds / 3600.0)) * sign

def scrape_stops():
	locations = get_locations(urlopen(MZKBB_LOCATION_URL))
	log.debug("Locations: " + repr(locations))
	for location in locations:
		location_page = urlopen(location['url'])
		for stop in get_stops(location_page):
			yield stop


if __name__ == "__main__":
	with open("stops.txt", "wb") as fh:
		log.info("Writing stops.txt")
		stops_csv = csv.DictWriter(fh, ['id', 'name', 'name', 'description', 'lattitude', 'longitude', 'zone_id', 'url'])
		[stops_csv.writerow(s) for s in scrape_stops()]

