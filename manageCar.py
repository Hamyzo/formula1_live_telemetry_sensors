from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime
import serial

client = MongoClient('mongodb://localhost:27000/')
db = client.rasp15

cars = db.cars


def parcel_scanned(ID):
    print(ID)
    car = cars.find_one({"_id": ObjectId(ID)})
    if car:
        print("car found")
        print(car)
    else:
        is_create = raw_input("Car not found, do you want to link this id to a new car? (y/n) ")
        if is_create == 'y':
            print("Please enter the following information")
            team = raw_input("team: ")
            driver = raw_input("driver: ")
            manufacturer = raw_input("manufacturer: ")
            number = raw_input("number: ")
            color = raw_input("team color: ")
            new_car = {
                "_id": ObjectId(ID),
                "team": team,
                "driver": driver,
                "manufacturer": manufacturer,
                "number": number,
                "color": color
            }

            print(new_car)

            db.cars.insert_one(new_car)
        else:
            print("Action aborted.")


PortRF = serial.Serial('/dev/ttyAMA0', 9600)
while True:
    ID = ""
    read_byte = PortRF.read()
    if read_byte == "\x02":
        for Counter in range(0, 12):
            read_byte = PortRF.read()
            ID = ID + str(read_byte)
        parcel_scanned(ID)
