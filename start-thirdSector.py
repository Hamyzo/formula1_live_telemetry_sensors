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
lap_dict = {}
if today_races.count() > 0:
    for idx, race in enumerate(today_races):
        print("{}) {}".format(idx + 1, race['country']))
    raceId = int(input('Please enter number of the race: '))
    raceId = ObjectId(races.find()[raceId - 1]['_id'])
    while True:
        is_scanning = raw_input('Scan a new car ? (y/n)')
        if is_scanning == "y":
            carId = scan_car()
            races.update(
                {
                    "_id": raceId,
                    "cars.car": ObjectId(carId)
                },
                {"$set":
                    {
                        "cars.$.status": "participating"
                    }
                }
            )
            allowed.append(ObjectId(carId))
            lap_dict[str(ObjectId(carId))] = 0
        else:
            print("Everything's ready")
            break
else:
    print("No race is scheduled for today")

##listen third sector
time_dict = {}
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
    print('onmessage lapPPPPP', lap_count)
    lap_dict[key_dict] = lap_count
    time_dict[key_dict] = datetime.strptime(value_dict, '%Y-%m-%d %H:%M:%S.%f')

'''client3 = mqtt.Client()
client3.connect('192.168.137.8', 1883, 60)
client3.on_message = on_message
client3.loop_start()
client3.subscribe('thirdSector', qos=0)'''

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
        if ObjectId(ID) in allowed:
            lap_dict[str(ObjectId(ID))] = lap_dict[str(ObjectId(ID))] + 1
            current_time = datetime.now()
            print('lap ', lap_dict[str(ObjectId(ID))])
            lapTimeJson = {
                '_id': str(ObjectId(ID)),
                'date': str(current_time),
                'raceId': str(raceId),
                'currentLap': lap_dict[str(ObjectId(ID))]
            }
            lapTime = json.dumps(lapTimeJson)
            clientPublish = mqtt.Client()
            clientPublish.connect('localhost', 1883, 60)
            clientPublish.publish('firstSector', lapTime)
            clientPublish.disconnect()
            allowed.remove(ObjectId(ID))
            if lap_dict[str(ObjectId(ID))]>1:
                sector_time = current_time - time_dict[str(ObjectId(ID))]
                print("sector time: ", sector_time.total_seconds())
                response = races.update(
                    {
                        "_id": ObjectId(raceId),
                        "cars.car": ObjectId(ID)
                    },
                    {"$push":
                        {
                            "cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))] - 2): sector_time.total_seconds()
                        }
                    }
                )
                print("if----------------------cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))]))
                print("Response: ", response)
            else:
                print('PRINTTTTTT', lap_dict[str(ObjectId(ID))])
                print("else----------------------cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))]))
        else:
            print('Not allowed')
client2.loop_stop()
'''client3.loop_stop()'''
client2.disconnect()
'''client3.disconnect()'''
