#!/usr/bin/env python2
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
	return [{
		"url": urljoin(base_url, el['href']),
		"name": el('font')[0].contents[0].strip(),
	} for el in els]

def get_stops(page):
	base_url = MZKBB_URL
	#if hasattr(page, 'geturl'):
	#	url = urlparse(page.geturl)
	#	base_url = urlunparse((url.scheme, url.netloc, '', '', '', ''))

	strainer = SoupStrainer('a', href=re.compile('^p_\d+'))
	els = BeautifulSoup(page, parseOnlyThese=strainer)
	strip_stop = re.compile("&nbsp.*")
	stops = []
	for el in els:
		stop = {
			"url": urljoin(base_url, el['href']),
			"name": strip_stop.sub("", el('font')[0].contents[0]),
			"id": el['href'][2:-6],
		}
		details = get_stop_details(stop['name'])
		stop["longitude"] = details["longitude"]
		stop["lattitude"] = details["lattitude"]
		stops.append(stop)
	return stops

def get_stop_details(name):
	gps_re = re.compile("(\d+).(\d+)'(\d+)\"\s*(\w)")
	qstring = cgi.escape(name).encode('ascii', 'xmlcharrefreplace').replace(" ", "+")
	url = urljoin(LB_URL, "/m/szukaj?q=" + qstring)
	log.debug("Retrieving GPS details from " + url)
	page = urlopen(url)

	url = BeautifulSoup(page).findAll("ul", attrs={"class": "links"})[0].findAll('a')[0]['href']
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
		soup = BeautifulSoup(page)
	
	log.debug(soup.findAll('div', id="peron-info"))
	info = soup.findAll('div', id="peron-info")[0]

	gps = info.findAll('p')[0].findAll('strong')[0].contents[0].strip()
	log.debug("GPS: " + repr(gps))
	gps = gps.split(', ', 2)[:2]

	log.debug("matching lon: " + repr(gps[0]))
	log.debug(gps_re.match(gps[0]))
	[d, m, s] = gps_re.match(gps[0]).groups()[:3]
	lon = dms_to_wgs84(int(d), int(m), int(s))
	log.debug("long: " + str(lon))

	log.debug("matching lon: " + repr(gps[1]))
	[d, m, s] = gps_re.match(gps[1]).groups()[:3]
	lat = dms_to_wgs84(int(d), int(m), int(s))
	log.debug("lat: " + str(lat))

	return {
		"longitude": lon,
		"lattitude": lat,
	}


def dms_to_wgs84(degress, minutes, seconds):
	return degress + (minutes / 60.0) + (seconds / 3600.0)

if __name__ == "__main__":
	locations = get_locations(urlopen(MZKBB_LOCATION_URL))
	log.debug("Locations: " + repr(locations))
	stops = []
	for location in locations:
		log.info("Retrieving stops for "+location['name'])
		log.debug("url: " + location['url'])
		page = urlopen(location['url'])
		stops.extend(get_stops(page))
	log.debug("Stops: " + repr(stops))
	log.info("Writing stops.txt")
	fh = open("stops.txt", 'wb')
	stops_csv = csv.DictWriter(fh, ['id', 'name', 'name', 'description', 'lattitude', 'longitude', 'zone_id', 'url'])
	[stops_csv.writerow(s) for s in stops]
	fh.close()

