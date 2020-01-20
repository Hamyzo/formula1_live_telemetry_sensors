from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import serial

client = MongoClient('mongodb://localhost:27000/')
db = client.rasp15

races = db.races

today_races = races.find({"date": datetime.today()})
if len(today_races) > 0:
    for idx, race in enumerate(today_races):
        print("{}) {}".format(idx + 1, race['country'], race['circuit']))

else:
    print("No race is scheduled for today")
