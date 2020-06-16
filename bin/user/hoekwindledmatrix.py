# Based on WindGuru plugin, portions copyright 2020 Claude Obahn
# Based on WindFinder plugin, portions copyright 2014 Matthew Wall

"""
This is a WeeWX extension that displays data on an LED matrix
"""

try:
	# Python 3
	import queue
except ImportError:
	# Python 2
	import Queue as queue
try:
	# Python 3
	from urllib.parse import urlencode
except ImportError:
	# Python 2
	from urllib import urlencode
import re
import sys
import time

import weewx
import weewx.units
from weeutil.weeutil import timestamp_to_string

VERSION = "0.1"

if weewx.__version__ < "3":
	raise weewx.UnsupportedFeature("weewx 3 is required, found %s" %
								   weewx.__version__)

try:
	# Test for new-style weewx logging by trying to import weeutil.logger
	import weeutil.logger
	import logging
	log = logging.getLogger(__name__)

	def logdbg(msg):
		log.debug(msg)

	def loginf(msg):
		log.info(msg)

	def logerr(msg):
		log.error(msg)

except ImportError:
	# Old-style weewx logging
	import syslog

	def logmsg(level, msg):
		syslog.syslog(level, 'HoekWind: %s' % msg)

	def logdbg(msg):
		logmsg(syslog.LOG_DEBUG, msg)

	def loginf(msg):
		logmsg(syslog.LOG_INFO, msg)

	def logerr(msg):
		logmsg(syslog.LOG_ERR, msg)

def _mps_to_knot(v):
	from_t = (v, 'meter_per_second', 'group_speed')
	return weewx.units.convert(from_t, 'knot')[0]


class HoekWindLEDMatrix(weewx.engine.StdPrint):

	# Override the default new_loop_packet member function:
	def new_loop_packet(self, event):
		packet = event.packet
		print "LOOP: ", timestamp_to_string(packet['dateTime']),
			"HoekWind=",  packet.get('windSpeed', 'N/A')
