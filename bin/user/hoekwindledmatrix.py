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
from PIL import Image, ImageFont, ImageDraw, ImageColor
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

def wheel(pos):
	"""Generate rainbow colors across 0-255 positions."""
	if pos < 85:
		return (pos * 3, 255 - pos * 3, 0)
	elif pos < 170:
		pos -= 85
		return (255 - pos * 3, 0, pos * 3)
	else:
		pos -= 170
		return (0, pos * 3, 255 - pos * 3)

class HoekWindLEDMatrix(weewx.engine.StdPrint):

	def __init__(self, engine, config_dict):
		logdbg("hoekwind init")

		# Create NeoPixel object with appropriate configuration.
		self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
		# Intialize the library (must be called once before other functions).
		self.strip.begin()

		self.windSpeeds = []

		#show a little into text
		for j in range(256):
			color = wheel(j & 255)
			self.displayText("SendIt", color)

#		red = (255, 0, 0)
#		green = (0, 255, 0)
#		blue = (0, 0, 255)

#		self.displayText('red', red)
#		time.sleep(1)
#		self.displayText('green', green)
#		time.sleep(1)
#		self.displayText('blue', blue)
#		time.sleep(1)


#		for windSpeed in range(1, 50):
#			self.displayWindSpeed(windSpeed, 123)
#			time.sleep(0.25)
#		for windAngle in range(0, 359, 15):
#			self.displayWindSpeed(15, windAngle)
#			time.sleep(0.25)

		self.clear()

		super(HoekWindLEDMatrix, self).__init__(engine, config_dict)

	# Override the default new_loop_packet member function:
	def new_loop_packet(self, event):
		packet = event.packet
		windSpeed = packet.get('windSpeed', 'N/A')
		if windSpeed != 'N/A':
			windSpeed = round(windSpeed)
			windDir = packet.get('windDir', 'N/A')

			self.windSpeeds.insert(0, windSpeed)
			while len(self.windSpeeds) > 44:
				self.windSpeeds.pop()
			windSpeedAvg = round(sum(self.windSpeeds) / len(self.windSpeeds))
			#loginf(windSpeed)
			#loginf(self.windSpeeds)
			#loginf(windSpeedAvg)

			self.displayWindSpeed(windSpeedAvg, windDir)

			#show a history of our speeds....
			i = 43
			for speed in self.windSpeeds:
				self.strip.setPixelColor(44*10+i, Color(*self.getWindSpeedColor(speed)))
				i=i-1
			self.strip.show()

	def displayWindSpeed(self, windSpeed, windDir):
		color = self.getWindSpeedColor(windSpeed)

		cardinal = self.getCardinal(windDir)

		base_path = os.path.dirname(os.path.realpath(__file__))
		big = ImageFont.load("/home/pi/hoeken/cherry-13-b.pil")
		kts = ImageFont.load("/home/pi/hoeken/cherry-10-r.pil")
		small = ImageFont.load("/home/pi/hoeken/cherry-10-b.pil")
		img = Image.new("RGB", (44, 11))

		d = ImageDraw.Draw(img)
		d.text((-1,-2), f"{windSpeed:2.0f}", font=big, fill=color)
		d.text((13, 1), f"kt", font=kts, fill=color)
		d.text((26, 1), f"{cardinal}", font=small, fill=color)

		img.save(f"/home/pi/hoeken/images/{windSpeed}-{cardinal}.png")

		self.displayImage(img);

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

		matrix = []
		for y in range(LED_ROWS):
			row = []
			for x in range(LED_COLS):
				r, g, b = pix[x,y]
				row.append(Color(r,g,b))
			matrix.append(row)
		self.displayMatrix(matrix)

	def displayText(self, text, color=(255,255,255)):
		base_path = os.path.dirname(os.path.realpath(__file__))
		fnt = ImageFont.load("/home/pi/hoeken/cherry-13-b.pil")

		txt = Image.new("RGB", (44, 11))
		d = ImageDraw.Draw(txt)
		d.text((-1,-1), text, font=fnt, fill=color)

		txt.save(f"/home/pi/hoeken/images/{text}.png")

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
#		val = round(val)
#		val = max(0, val)
#		val = min(50, val)

#		return ImageColor.getrgb(f"#{windSpeedColors[val]}")

		if val < 5:
			hex = "#808080"
		elif val < 10:
			hex = "#00ffff"
		elif val < 15:
			hex = "#ffff00"
		elif val < 20:
			hex = "#00ff00"
		elif val < 25:
			hex = "#ff8000"
		elif val < 30:
			hex = "#ff0000"
		elif val < 35:
			hex = "#ff007f"
		elif val < 40:
			hex = "#ff00ff"
		else:
			hex = "#0000ff"
#
		return ImageColor.getrgb(hex)
