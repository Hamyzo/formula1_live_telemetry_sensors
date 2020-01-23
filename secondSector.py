from datetime import datetime, timedelta
from pymongo import MongoClient
from bson.objectid import ObjectId
import serial
import time
import paho.mqtt.client as mqtt
import json

client = MongoClient('mongodb://localhost:27000/')
db = client.rasp15
races = db.races

##listen Raspberry at third sector
allowed = []
time_dict = {}
lap_dict = {}
lap_count = 0
race_id = 0

def on_message(client, data, message):
	global race_id
	global lap_count
	messageJson = json.loads(message.payload)
	allowed.append(ObjectId(messageJson["_id"]))
	key_dict = messageJson["_id"]
	value_dict = str(messageJson["date"])
	race_id = messageJson["raceId"]
	lap_count = messageJson["currentLap"]
	print('lap ', lap_count)
	lap_dict[key_dict] = lap_count
	time_dict[key_dict] = datetime.strptime(value_dict, '%Y-%m-%d %H:%M:%S.%f')
client = mqtt.Client()
client.connect('192.168.137.245', 1883, 60)
client.on_message = on_message
client.loop_start()
client.subscribe('firstSector', qos=0)

##publish
PortRF = serial.Serial('/dev/ttyAMA0',9600)
while True:
	ID = ""
	read_byte = PortRF.read()
	if read_byte=="\x02":
		for Counter in range(0,12):
			read_byte=PortRF.read()
			ID = ID + str(read_byte)
		current_time = datetime.now()
		lapTimeJson = {
			'_id': str(ObjectId(ID)),
			'date': str(current_time),
			'raceId': str(race_id),
			'currentLap': lap_dict[str(ObjectId(ID))]
		}
		lapTime = json.dumps(lapTimeJson)
		sector_time = current_time - time_dict[str(ObjectId(ID))]
		if ObjectId(ID) in allowed:
			clientPublish = mqtt.Client()
			clientPublish.connect('localhost', 1883, 60)
			clientPublish.publish('secondSector', lapTime)
			clientPublish.disconnect()
			allowed.remove(ObjectId(ID))
			print("second sector time: ", sector_time.total_seconds())
			response = races.update_one(
				{
					"_id": ObjectId(race_id),
					"cars.car": ObjectId(ID)
				},
				{"$push":
					{
						"cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))] - 1): sector_time.total_seconds()
					}
				}
			)
			print("if----------------------cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))]))
			print("Response: ", response)
		else:
			print('Not allowed')
client.loop_stop()
client.disconnect()