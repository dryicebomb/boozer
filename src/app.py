#!/usr/bin/python
# -*- coding: utf-8 -*

import os
import time
import math
import logging
import scrollphat
import RPi.GPIO as GPIO
from flowmeter import *
import beer_database as db
import bartwitter
import requests
import ConfigParser
from pushbullet import Pushbullet
import bar_mqtt

DEGREES="°"
DISABLED="disabled"

CONFIG_FILE="./config.ini"
config = ConfigParser.ConfigParser()
config.read(CONFIG_FILE)

#pb = Pushbullet(config.get("Pushbullet","api_key"))

TAP1_PIN=config.getint("Taps","tap1_gpio_pin")
TAP2_PIN=config.getint("Taps","tap2_gpio_pin")
TAP3_PIN=config.getint("Taps","tap3_gpio_pin")
TAP4_PIN=config.getint("Taps","tap4_gpio_pin")

GPIO.setmode(GPIO.BCM) # use real GPIO numbering

# Setup the Taps
GPIO.setup(TAP1_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(TAP2_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(TAP3_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(TAP4_PIN,GPIO.IN, pull_up_down=GPIO.PUD_UP)

# set up the flow meters
taps = []
tap1 = FlowMeter( "not metric", [config.get("Taps","tap1_beer_name")], tap_id=4)
tap2 = FlowMeter( "not metric", [config.get("Taps","tap2_beer_name")], tap_id=3)
tap3 = FlowMeter( "not metric", [config.get("Taps","tap3_beer_name")], tap_id=2)
tap4 = FlowMeter( "not metric", [config.get("Taps","tap4_beer_name")], tap_id=1)
taps = {tap1,tap2,tap3,tap4}

# More config
temperature_url = config.get("Temperature","endpoint")

SCROLLPHAT_ENABLED = False
if config.get("Scrollphat",'enabled') == "True":
  scrollphat.set_brightness(7)
  print "[ENABLED] scrollphat"
else:
  print "[DISABLED] scrollphat (%s)" % config.get("Scrollphat",'enabled')

def get_temperature():
  global temperature_url
  try:
    r = requests.get(temperature_url)
    if r.status_code == 200:
      return r.text
    else:
      return "error_http"
  except:
    return "error"

def record_pour(tap_id, pour):
  # update sqlite database
  db.update_tap(tap_id,pour)
  print "[TAP ",tap_id, "] UPDATED IN DATABASE"
  # TODO: Post to influx here to show most recent pour

def update_mqtt(tap_id):
  global config
  broker = config.get("Mqtt","broker")
  percent= db.get_percentage100(tap_id)
  topic = "bar/tap%s" % str(tap_id)
  bar_mqtt.pub_mqtt(broker,topic,str(percent))

# Update the values in mqtt
if config.getboolean("Mqtt","enabled"):
  print "[Mqtt] enabled."
  update_mqtt(1)
  update_mqtt(2)
  update_mqtt(3)
  update_mqtt(4)
else:
  print "[Mqtt] disabled."
  
def register_tap1(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if tap1.enabled == True:
    tap1.update(currentTime)
def register_tap2(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if tap2.enabled == True:
    tap2.update(currentTime)
def register_tap3(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if tap3.enabled == True:
    tap3.update(currentTime)
def register_tap4(channel):
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  if tap4.enabled == True:
    tap4.update(currentTime)


def logit(somestr):
  return


def tweetPour(theTweet):
  bartwitter.post_tweet(theTweet)
  print "[THE TWEET] " +theTweet

# TODO, look into this and how to pass parameters to doAClick function
GPIO.add_event_detect(TAP4_PIN, GPIO.RISING, callback=register_tap1, bouncetime=20) # TAP 4
GPIO.add_event_detect(TAP3_PIN, GPIO.RISING, callback=register_tap2, bouncetime=20) # TAP 3
GPIO.add_event_detect(TAP2_PIN, GPIO.RISING, callback=register_tap3, bouncetime=20) # TAP 2
GPIO.add_event_detect(TAP1_PIN, GPIO.RISING, callback=register_tap4, bouncetime=20) # TAP 1

#volume_remaining = str(round(db.get_percentage(4),3) * 100)
#print "TAP 4 remaining! %s " % volume_remaining

old_pour=0
# main loop
scrollphat_cleared = True


# Initial info
print "[Temperature] " + get_temperature()

while True:
  # Handle keyboard events
  currentTime = int(time.time() * FlowMeter.MS_IN_A_SECOND)
  for tap in taps:
    if tap.getBeverage() == DISABLED:
      pass
    if tap.thisPour > 0.0:
      pour_size = round(tap.thisPour * FlowMeter.PINTS_IN_A_LITER, 3)
      pour_size2 = round(tap.thisPour * FlowMeter.PINTS_IN_A_LITER, 2)
      if pour_size != old_pour:
        print "Tap: %s\t Poursize: %s vs %s" % (tap.get_tap_id(),  pour_size, str(old_pour)) 
        scrollphat.set_brightness(7)
        scrollphat.write_string(str(pour_size2).replace("0.","."))
        old_pour = pour_size
        scrollphat_cleared = False
    if (tap.thisPour > 0.23 and currentTime - tap.lastClick > 10000): # 10 seconds of inactivity causes a tweet
      print "[formattedpour]:", tap.getFormattedThisPour()
      print "[poursize]:", tap.thisPour
      pour_size = round(tap.thisPour * FlowMeter.PINTS_IN_A_LITER, 3)
      record_pour(tap.get_tap_id(), pour_size)


      volume_remaining = str(round(db.get_percentage(tap.get_tap_id()),3) * 100)
      tweet = "I just poured " + tap.getFormattedThisPour()  + " of " + tap.getBeverage() + " from Tap " + str(tap.get_tap_id()) + " (" + volume_remaining + "% remaining)"+  " at a cold " + str(get_temperature()) + DEGREES
      logit(tweet)
      tweetPour(tweet)
      print "[POUR HAS BEEN TWEETED]"
      tap.thisPour = 0.0
      scrollphat.clear()
      if config.getboolean("Mqtt","enabled"):
        update_mqtt(tap.get_tap_id())
      


    if tap.thisPour > 0.05:
#      print currentTime - tap.lastClick 
      print "[TAP "+ str(tap.get_tap_id())  +"]\t" + str(tap.thisPour)
    
    # reset flow meter after each pour (2 secs of inactivity)
    if (tap.thisPour <= 0.23 and currentTime - tap.lastClick > 2000):
#      print "[CLEARING SCROLLPHAT]"
#      scrollphat.clear()
      tap.thisPour = 0.0
    if (currentTime - tap.lastClick > (2000*30)) and (SCROLLPHAT_ENABLED == True) and (scrollphat_cleared == False):
      scrollphat.clear()
      print "[CLEARING SCROLLPHAT]"
      
  time.sleep(0.01)    
