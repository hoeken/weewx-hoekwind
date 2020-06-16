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

from rpi_ws281x import PixelStrip, Color
from PIL import Image, ImageFont, ImageDraw
import random

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

LED_ROWS = 11
LED_COLS = 44
LED_COUNT = LED_ROWS * LED_COLS		# Number of LED pixels.
LED_PIN = 18		  # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10		  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False	# True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL = 0	   # set to '1' for GPIOs 13, 19, 41, 45 or 53

class HoekWindLEDMatrix(weewx.engine.StdPrint):

	def __init__(self, engine, config_dict):
		loginf("hoekwind init")
		
		# Create NeoPixel object with appropriate configuration.
		self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
		# Intialize the library (must be called once before other functions).
		self.strip.begin()
		
		super(HoekWindLEDMatrix, self).__init__(engine, config_dict)

	# Override the default new_loop_packet member function:
	def new_loop_packet(self, event):
		packet = event.packet
		windSpeed = _mps_to_knot(packet.get('windSpeed', 'N/A'))
		outputString = f"{windSpeed} kts"
		loginf(outputString)
		#self.displayText(outputString)
		self.colorWipe(Color(255,0,0), 5)
		
	# Define functions which animate LEDs in various ways.
	def colorWipe(color, wait_ms=50):
		"""Wipe color across display a pixel at a time."""
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, color)
			self.strip.show()
			time.sleep(wait_ms / 1000.0)

	def matrix_to_array(matrix):
		arr = []
		rows = len(matrix)
		cols = len(matrix[0])
		
		for r in range(rows):
			for c in range(cols):
				if r % 2 == 1:
					arr.append(matrix[r][LED_COLS-1-c])
				else:
					arr.append(matrix[r][c])

		return arr

	def displayMatrix(matrix):
		arr = matrix_to_array(matrix)
		for i in range(len(arr)):
			self.strip.setPixelColor(i, arr[i])

		self.strip.show()

	def displayImage(im):

		rgb_im = im.convert('RGB')
		pix = rgb_im.load()

		#print(im.size)
		
		matrix = []
		for y in range(LED_ROWS):
			row = []
			for x in range(LED_COLS):
				r, g, b = pix[x,y]
				row.append(Color(r,g,b))
			matrix.append(row)
		
		displayMatrix(matrix)

	def displayText(text):
		base = Image.new("RGBA", (44, 11))
		txt = Image.new("RGBA", (44, 11))
		fnt = ImageFont.load('cherry-13-b.pil')
		d = ImageDraw.Draw(txt)
		
		kts = random.randint(10, 25)
		
		d.text((0,-1), text, font=fnt, fill=(255,255,255,255))
		im = Image.alpha_composite(base, txt)
		
		displayImage(im);


	def clear():
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, Color(0,0,0))
		self.strip.show()
			
			
