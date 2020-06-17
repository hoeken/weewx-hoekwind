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
import os

import weewx
import weewx.units
from weeutil.weeutil import timestamp_to_string

from rpi_ws281x import PixelStrip, Color
from PIL import Image, ImageFont, ImageDraw
import random
import time

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

cardinalMin = {
	'N' : 348.75,
	'NNE' : 11.25,
	'NE' : 33.75,
	'ENE' : 56.25,
	'E' : 78.75,
	'ESE' : 101.25,
	'SE' : 123.75,
	'SSE' : 146.25,
	'S' : 168.75,
	'SSW' : 191.25,
	'SW' : 213.75,
	'WSW' : 236.25,
	'W' : 258.75,
	'WNW' : 281.25,
	'NW' : 303.75,
	'NNW' : 326.25
}

cardinalMax = {
	'N' : 11.25,
	'NNE' : 33.75,
	'NE' : 56.25,
	'ENE' : 78.75,
	'E' : 101.25,
	'ESE' : 123.75,
	'SE' : 146.25,
	'SSE' : 168.75,
	'S' : 191.25,
	'SSW' : 213.75,
	'SW' : 236.25,
	'WSW' : 258.75,
	'W' : 281.25,
	'WNW' : 303.75,
	'NW' : 326.25,
	'NNW' : 348.75
}

windSpeedColors = {
	0 : "FFFFFF",
	1 : "FFFFFF",
	2 : "FFFFFF",
	3 : "FFFFFF",
	4 : "FFFFFF",
	5 : "EFFEFE",
	6 : "E0FDFC",
	7 : "C1FCF9",
	8 : "7EF8F3",
	9 : "60F8E1",
	10 : "45FAA2",
	11 : "34FB79",
	12 : "1BFD3F",
	13 : "0DFE1F",
	14 : "1DFD00",
	15 : "5BFA00",
	16 : "82F700",
	17 : "9AF600",
	18 : "CAF300",
	19 : "FAF000",
	20 : "FFC60A",
	21 : "FFAC10",
	22 : "FF7C1B",
	23 : "FF721D",
	24 : "FF4F25",
	25 : "FF3033",
	26 : "FF2D3E",
	27 : "FF2464",
	28 : "FF1E7A",
	29 : "FF1890",
	30 : "FF14A0",
	31 : "FF0DBB",
	32 : "FF0ACA",
	33 : "FF07D6",
	34 : "FF07D8",
	35 : "FF04E7",
	36 : "FF03EF",
	37 : "FF02F5",
	38 : "FF01FB",
	39 : "EA0AFF",
	40 : "E70BFF",
	41 : "D215FF",
	42 : "C31DFF",
	43 : "B026FF",
	44 : "AD27FF",
	45 : "9C2FFF",
	46 : "9232FF",
	47 : "8B33FF",
	48 : "8534FF",
	49 : "7D35FF",
	50 : "7935FF"
}

def hex_to_rgb(value):
	value = value.lstrip('#')
	lv = len(value)
	return tuple(int(value[i:i+lv//3], 16) for i in range(0, lv, lv//3))

class HoekWindLEDMatrix(weewx.engine.StdPrint):

	def __init__(self, engine, config_dict):
		logdbg("hoekwind init")

		# Create NeoPixel object with appropriate configuration.
		self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
		# Intialize the library (must be called once before other functions).
		self.strip.begin()

		self.displayText("SendIt")

#		for windSpeed in range(1, 50):
#			self.displayWindSpeed(windSpeed, 123)
#			time.sleep(0.5)

		super(HoekWindLEDMatrix, self).__init__(engine, config_dict)

	# Override the default new_loop_packet member function:
	def new_loop_packet(self, event):
		packet = event.packet
		windSpeed = packet.get('windSpeed', 'N/A')
		if windSpeed != 'N/A':
			windSpeed = round(windSpeed)
			windDir = packet.get('windDir', 'N/A')
			self.displayWindSpeed(windSpeed, windDir)

	def displayWindSpeed(self, windSpeed, windDir):
		windSpeedColorHex = self.getWindSpeedColor(windSpeed)
		rgb = hex_to_rgb(windSpeedColorHex)
		windSpeedColor = Color(rgb[0], rgb[1], rgb[2])

		cardinal = self.getCardinal(windDir)
		loginf(f"{windDir} {cardinal} #{windSpeedColorHex}")

		outputString = f"{windSpeed:2.0f} {cardinal}"
		loginf(outputString)
		self.displayText(outputString, windSpeedColor)
		#red = Color(255,0,0)
		#self.colorWipe(red, 5)

	# Define functions which animate LEDs in various ways.
	def colorWipe(self, color, wait_ms=50):
		"""Wipe color across display a pixel at a time."""
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, color)
			self.strip.show()
			time.sleep(wait_ms / 1000.0)

	def matrix_to_array(self, matrix):
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

	def displayMatrix(self, matrix):
		arr = self.matrix_to_array(matrix)
		for i in range(len(arr)):
			self.strip.setPixelColor(i, arr[i])

		self.strip.show()

	def displayImage(self, im):

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
		self.displayMatrix(matrix)

	def displayText(self, text, color=Color(255,255,255)):
		base_path = os.path.dirname(os.path.realpath(__file__))
		fnt = ImageFont.load("/home/pi/hoeken/cherry-13-b.pil")

		txt = Image.new("RGBA", (44, 11))
		d = ImageDraw.Draw(txt)
		d.text((-1,-1), text, font=fnt, fill=color)

		self.displayImage(txt);


	def clear(self):
		for i in range(self.strip.numPixels()):
			self.strip.setPixelColor(i, Color(0,0,0))
		self.strip.show()

	def getCardinal(self, degrees):
		if degrees >= cardinalMin['N'] or degrees <= cardinalMax['N']:
			return 'N';

		for cardinal, min in cardinalMin.items():
			max = cardinalMax[cardinal]

			if degrees >= min and degrees <= max:
				return cardinal
		return '?'

	def getWindSpeedColor(self, val):
		val = round(val)
		val = max(0, val)
		val = min(50, val)

		return windSpeedColors[val]
