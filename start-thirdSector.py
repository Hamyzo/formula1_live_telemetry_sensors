from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import serial
import paho.mqtt.client as mqtt
import json
import socketio

#----------------- Connecting to the web-socket -----------------#
sio = socketio.Client()


@sio.event
def connect():
    print('connection established')


@sio.event
def disconnect():
    print('disconnected from server')


sio.connect('http://localhost:3015')

#----------------- Connecting to the MongoDB -----------------#
client = MongoClient('mongodb://localhost:27000/')
db = client.rasp15
races = db.races


#----------------- Scanning the car(card) -----------------#
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


#----------------- Displaying pending races -----------------#
today_races = races.find({"status": "pending"})
allowed = []
raceId = 0
lapsNum = 0
carsNum = 0
lap_dict = {}
is_last = False
if today_races.count() > 0:
    for idx, race in enumerate(today_races):
        print("{}) {}".format(idx + 1, race['country']))
    raceId = int(input('Please enter number of the race: '))
    lapsNum = races.find()[raceId - 1]['nb_laps']
    raceId = ObjectId(races.find()[raceId - 1]['_id'])
    races.update(
        {
            "_id": raceId
        },
        {"$set":
            {
                "status": "ongoing"
            }
        }
    )
    # ----------------- Adding cars to the race -----------------#
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
            carsNum = carsNum + 1
            allowed.append(ObjectId(carId))
            # sio.emit('raspberry message', {'response': 'update'})
            lap_dict[str(ObjectId(carId))] = 0
        else:
            print("Everything's ready")
            break
else:
    print("No race is scheduled for today")

#----------------- Listening to the second sector -----------------#
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
    lap_dict[key_dict] = lap_count
    time_dict[key_dict] = datetime.strptime(value_dict, '%Y-%m-%d %H:%M:%S.%f')
client = mqtt.Client()
client.connect('192.168.137.177', 1883, 60)
client.on_message = on_message
client.loop_start()
client.subscribe('secondSector', qos=0)

# ----------------- Publishing car's time on the current sector -----------------#
PortRF = serial.Serial('/dev/ttyAMA0', 9600)
while True:
    ID = ""
    read_byte = PortRF.read()
    if read_byte == "\x02":
        for Counter in range(0, 12):
            read_byte = PortRF.read()
            ID = ID + str(read_byte)
        #----------------- if it's not a last lap -----------------#
        if ObjectId(ID) in allowed and is_last == False and ObjectId(ID) != '303030303030303030303030':
            lap_dict[str(ObjectId(ID))] = lap_dict[str(ObjectId(ID))] + 1
            current_time = datetime.now()
            print('lap ', lap_dict[str(ObjectId(ID))])
            if lap_dict[str(ObjectId(ID))] == lapsNum:
                is_last = True
            lapTimeJson = {
                '_id': str(ObjectId(ID)),
                'date': str(current_time),
                'raceId': str(raceId),
                'currentLap': lap_dict[str(ObjectId(ID))]
            }
            lapTime = json.dumps(lapTimeJson)
            clientPublish = mqtt.Client()
            clientPublish.connect('localhost', 1883, 60)
            clientPublish.publish('thirdSector', lapTime)
            clientPublish.disconnect()
            allowed.remove(ObjectId(ID))
            if lap_dict[str(ObjectId(ID))] > 1:
                sector_time = current_time - time_dict[str(ObjectId(ID))]
                print("third sector time: ", sector_time.total_seconds())
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
                # sio.emit('raspberry message', {'response': 'update'})
                print("----------------------cars.$.lap_times.{}".format(lap_dict[str(ObjectId(ID))]))
        #----------------- if it's a last lap -----------------#
        elif ObjectId(ID) in allowed and is_last == True and carsNum > 0:
            lap_dict[str(ObjectId(ID))] = lap_dict[str(ObjectId(ID))] + 1
            current_time = datetime.now()
            allowed.remove(ObjectId(ID))
            sector_time = current_time - time_dict[str(ObjectId(ID))]
            print("third sector time: ", sector_time.total_seconds())
            carsNum = carsNum - 1
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
            sio.emit('raspberry message', {'response': 'update'})
            races.update(
                {
                    "_id": ObjectId(raceId),
                    "cars.car": ObjectId(ID)
                },
                {"$set":
                    {
                        "cars.$.status": "finished"
                    }
                }
            )
            print("-------------It was your final lap---------------")
            races.update(
                {
                    "_id": raceId
                },
                {"$set":
                    {
                        "status": "finished"
                    }
                }
            )
        #----------------- if car can't pass this sector-----------------#
        elif ObjectId(ID) not in allowed and is_last == False:
            print("NOT ALLOWED")
        #----------------- if race is finished -----------------#
        elif ObjectId(ID) not in allowed and is_last == True and carsNum == 0:
            print("Race is finished")
client.loop_stop()
client.disconnect()
sio.disconnect()
