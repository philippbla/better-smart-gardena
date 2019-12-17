#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jun  3 15:34:43 2019

@author: philipp
"""

# !/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun May 26 16:24:09 2019

@author: philipp
"""
import configparser
import datetime
import inspect
import json
import os
import sqlite3
from pytz import timezone
import requests


    

def set_script_folder_path():
    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path = os.path.dirname(os.path.abspath(filename))
    os.chdir(path)


set_script_folder_path()

username = ''
password = ''


def initialize_program():
    global username
    global password

    config = configparser.ConfigParser()
    config.read('config.ini')

    username = config['DEFAULT']['GARDENA_USERNAME']
    password = config['DEFAULT']['GARDENA_PASSWORD']


def get_gardena_token_user_id(username, password):
    data = '{{"data":{{"type":"token","attributes":{{"username":"{}","password":"{}"}}}}}}'.format(username, password)

    response = requests.post('https://smart.gardena.com/v1/auth/token', data=data)

    json_data = json.loads(response.text)
    return json_data.get('data').get('id'), json_data.get('data').get('attributes').get('user_id')


def get_location_id(token, user_id):
    headers = {
        'authorization': 'Bearer {token}'.format(token=token),
        'authorization-provider': 'husqvarna',
    }

    params = (
        ('locationId', 'null'),
        ('user_id', user_id),
    )

    response = requests.get('https://smart.gardena.com/v1/locations', headers=headers, params=params)
    json_data = json.loads(response.text)
    return json_data.get('locations')[0].get('id')


def get_device_id_for_device(token, location_id, device_name):
    headers = {
        'authorization': 'Bearer {token}'.format(token=token),
        'authorization-provider': 'husqvarna',
    }

    params = (
        ('locationId', location_id),
    )

    response = requests.get('https://smart.gardena.com/v1/devices', headers=headers, params=params)
    json_data = json.loads(response.text)
    for i in range(len(json_data.get('devices'))):
        if json_data.get('devices')[i].get('name') == device_name:
            output = json_data.get('devices')[i].get('id')
    return output


def convert_my_iso_8601(iso_8601, tz_info):
    assert iso_8601[-1] == 'Z'
    iso_8601 = iso_8601[:-1] + '000'
    iso_8601_dt = datetime.datetime.strptime(iso_8601, '%Y-%m-%dT%H:%M:%S.%f')
    return iso_8601_dt.replace(tzinfo=timezone('UTC')).astimezone(tz_info).replace(tzinfo=None, microsecond=0)


def get_last_sync_time(token, location_id, device_id):
    headers = {
        'authorization': 'Bearer {token}'.format(token=token),
        'authorization-provider': 'husqvarna',
    }

    params = (
        ('locationId', location_id),
    )

    response = requests.get('https://smart.gardena.com/v1/devices/{}'.format(device_id), headers=headers, params=params)
    json_data = json.loads(response.text)
    for i in range(len(json_data.get('devices').get('abilities')[0].get('properties'))):
        if json_data.get('devices').get('abilities')[0].get('properties')[i].get('name') == 'last_time_online':
            time = json_data.get('devices').get('abilities')[0].get('properties')[i].get('value')
    return convert_my_iso_8601(time, timezone('CET'))


def write_sensor_info_to_db(last_sync_time, air_temperature, soil_temperature, humidity, light):
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE sensor
                         (date timestamp , air_temperature_in_c numeric, soil_temperature_in_c numeric, soil_mositure_in_p numeric, light_in_lux numeric)''')
    except sqlite3.OperationalError:
        pass
    c.execute('SELECT DATE FROM sensor ORDER BY DATE DESC limit 1')
    if list(c) == []:
        c.execute("INSERT INTO sensor VALUES (?, ?, ?, ?, ?)",
                  (last_sync_time, air_temperature, soil_temperature, humidity, light))
    time_last_record = c.execute('SELECT DATE FROM sensor ORDER BY DATE DESC limit 1').fetchone()[0]
    if datetime.datetime.strptime(time_last_record, '%Y-%m-%d %H:%M:%S') < last_sync_time:
        c.execute("INSERT INTO sensor VALUES (?, ?, ?, ?, ?)",
                  (last_sync_time, air_temperature, soil_temperature, humidity, light))
    conn.commit()
    conn.close()


def get_sensor_information(token, location_id, device_id):
    headers = {
        'authorization': 'Bearer {token}'.format(token=token),
        'authorization-provider': 'husqvarna',
    }

    params = (
        ('locationId', location_id),
    )

    response = requests.get('https://smart.gardena.com/v1/devices/{}'.format(device_id), headers=headers, params=params)
    json_data = json.loads(response.text)
    for i in range(len(json_data.get('devices').get('abilities'))):
        if json_data.get('devices').get('abilities')[i].get('name') == 'ambient_temperature':
            air_temperature = json_data.get('devices').get('abilities')[i].get('properties')[0].get('value')
        if json_data.get('devices').get('abilities')[i].get('name') == 'soil_temperature':
            soil_temperature = json_data.get('devices').get('abilities')[i].get('properties')[0].get('value')
        if json_data.get('devices').get('abilities')[i].get('name') == 'humidity':
            humidity = json_data.get('devices').get('abilities')[i].get('properties')[0].get('value')
        if json_data.get('devices').get('abilities')[i].get('name') == 'light':
            light = json_data.get('devices').get('abilities')[i].get('properties')[0].get('value')
    return air_temperature, soil_temperature, humidity, light


def write_token_to_txt(username, password):
    token, user_id = get_gardena_token_user_id(username, password)
    with open('token+user_id.txt', 'w') as f:
        f.write(token+','+user_id)
        

def get_response_code(token, user_id):
    headers = {
            'authorization': 'Bearer {token}'.format(token=token),
            'authorization-provider': 'husqvarna',
    }

    params = (
            ('locationId', 'null'),
            ('user_id', user_id),
    )

    response = requests.get('https://smart.gardena.com/v1/locations', headers=headers, params=params)
    return response


def token_handling(username, password):
    try:
        with open('token+user_id.txt') as f:
            txt = f.readline()
            token, user_id = txt.split(',')
    except FileNotFoundError:
        write_token_to_txt(username, password)
        
    response = get_response_code(token, user_id)  
    if response.status_code == 403:
        write_token_to_txt(username, password)
    return token, user_id


initialize_program()

token, user_id = token_handling(username, password)

location_id = get_location_id(token, user_id)

device_id = get_device_id_for_device(token, location_id, 'Sensor')

last_sync_time = get_last_sync_time(token, location_id, device_id)

air_temperature, soil_temperature, humidity, light = get_sensor_information(token, location_id, device_id)

write_sensor_info_to_db(last_sync_time, air_temperature, soil_temperature, humidity, light)