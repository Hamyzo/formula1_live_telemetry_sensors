import serial
import time
import paho.mqtt.client as mqtt
import json

##listen Raspberry at second sector
allowed = []
def on_message(client, data, message):
	print("Received: "+ str(message.payload) + "on topic" + message.topic)
	allowed.append(json.loads(message.payload))
	print("Allowed list updated: ", allowed)
client = mqtt.Client()
client.connect('192.168.137.200', 1883, 60)
client.on_message = on_message
client.loop_start()
client.subscribe('firstSector', qos=0)

##publish
notallowed = []
PortRF = serial.Serial('/dev/ttyAMA0',9600)
while True:
	ID = ""
	read_byte = PortRF.read()
	if read_byte=="\x02":
		for Counter in range(0,12):
			read_byte=PortRF.read()
			ID = ID + str(read_byte)
		lapTimeJson = '{ "_id": ', ObjectId(ID) ,', "date": ', datetime.now(),' }'
		lapTime = str(lapTimeJson)
		if ID in allowed and ID not in notallowed:
			clientPublish = mqtt.Client()
			clientPublish.connect('localhost', 1883, 60)
			clientPublish.publish('secondSector', lapTime)
			clientPublish.disconnect()
			allowed.remove(ID)
			print('Allowed')
		else:
			print('Not allowed')
client.loop_stop()
client.disconnect()