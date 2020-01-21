from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import serial
import paho.mqtt.client as mqtt
import json

client = MongoClient('mongodb://localhost:27000/')
db = client.rasp15
races = db.races


def scan_car():
    PortRF = serial.Serial('/dev/ttyAMA0', 9600)
    while True:
        ID = ""
        read_byte = PortRF.read()
        if read_byte == "\x02":
            for Counter in range(0, 12):
                read_byte = PortRF.read()
                ID = ID + str(read_byte)
            print(ID)
            return (ID)


today_races = races.find({"status": "pending"})
allowed = []
raceId = 0
if today_races.count() > 0:
    for idx, race in enumerate(today_races):
        print("{}) {}".format(idx + 1, race['country']))
    raceId = int(input('Please enter number of the race: '))
    while True:
        is_scanning = raw_input('Scan a new car ? (y/n)')
        if is_scanning == "y":
            carId = scan_car()
            races.update(
                {
                    "_id": ObjectId(races.find()[raceId - 1]['_id']),
                    "cars.car": ObjectId(carId)
                },
                {"$set":
                    {
                        "cars.$.status": "participating"
                    }
                }
            )
            allowed.append(ObjectId(carId))
            raceId = ObjectId(races.find()[raceId - 1]['_id'])
        else:
            print("Everything's ready")
            break
else:
    print("No race is scheduled for today")

lap_count = 0
##listen third sector
def on_message(client, data, message):
    print("Received: " + str(message.payload) + "on topic" + message.topic)
    messageJson = json.loads(message.payload)
    allowed.append(str(message.payload))
    print("Allowed list updated: ", allowed)
client3 = mqtt.Client()
client3.connect('192.168.137.8', 1883, 60)
client3.on_message = on_message
client3.loop_start()
client3.subscribe('thirdSector', qos=0)

##listen second sector
client2 = mqtt.Client()
client2.connect('192.168.137.245', 1883, 60)
client2.on_message = on_message
client2.loop_start()
client2.subscribe('secondSector', qos=0)

##publish
PortRF = serial.Serial('/dev/ttyAMA0', 9600)
while True:
    ID = ""
    read_byte = PortRF.read()
    if read_byte == "\x02":
        for Counter in range(0, 12):
            read_byte = PortRF.read()
            ID = ID + str(read_byte)
        lapTimeJson = '{ "_id": ' + str(ObjectId(ID)) + ', "date": ' + str(datetime.now()) + ' }'
        lapTime = str(lapTimeJson)
        print("ID: ", ID)
        print("Allowed: ", allowed)
        if ObjectId(ID) in allowed:
            clientPublish = mqtt.Client()
            clientPublish.connect('localhost', 1883, 60)
            clientPublish.publish('firstSector', lapTime)
            clientPublish.disconnect()
            allowed.remove(ObjectId(ID))
            races.update(
                {
                    "_id": raceId,
                    "cars.car": ObjectId(ID)
                },
                {"$push":
                    {
                        "cars.$.lap_times.{}".format(lap_count): 20
                    }
                }
            )
            lap_count = lap_count + 1
        else:
            print('Not allowed')
client2.loop_stop()
client3.loop_stop()
client2.disconnect()
client3.disconnect()
