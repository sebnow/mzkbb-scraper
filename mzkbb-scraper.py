#!/usr/bin/env python
from BeautifulSoup import BeautifulSoup, SoupStrainer
from urllib2 import urlopen
import re

MZKBB_URL = "http://www.mzkb-b.internetdsl.pl"

def get_stops():
	strain_stops = SoupStrainer('a', href=re.compile('^p_.*'))
	stops_body = urlopen("http://www.mzkb-b.internetdsl.pl/m_1.htm")
	stop_els = BeautifulSoup(stops_body, parseOnlyThese=strain_stops)
	strip_stop = re.compile("&nbsp.*")
	return [{
		"url": el['href'],
		"name": '/'.join(MZKBB_URL, strip_stop.sub("", el('font')[0].contents[0])),
		"id": el['href'][2:-6],
	} for el in stop_els]

if __name__ == "__main__":
	stops = get_stops()
	print(stops)

