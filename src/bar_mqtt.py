#!/usr/bin/python

import paho.mqtt.client as paho
from random import randint

class BoozerMqtt():
    def __init__(self, brokerhost, port = 1883):
        self.broker = brokerhost
        self.port = port

    def pub_mqtt(self, topic,value):
        client1= paho.Client("control1")                           #create client object
        client1.connect(self.broker,self.port)                                 #establish connection
        print "[MQTT BROKER CONNECTION SUCCESSFULL] topic: %s | value: %s " % (topic,value)
        return client1.publish(topic,value)                   #publish

    def get_value(self,topic):
        client1= paho.Client("control1")                           #create client object
        client1.connect(self.broker,self.port)                                 #establish connection
        return str(client1.get(topic))
