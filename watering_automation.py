#!/usr/bin/env python3
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
import sys
import time as wait_time

import math
import numpy as np
import pandas as pd
import requests


def set_script_folder_path():
    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path = os.path.dirname(os.path.abspath(filename))
    os.chdir(path)


set_script_folder_path()

mode = ''
temperature_water_table = []
list_of_valves = {}
watering_radius = 0
latitude = 0
longitude = 0
username = ''
password = ''
api_key = ''
min_soil_moisture = 0
min_frequency_days = 0
min_watering_time = 0

def initialize_program():
    global mode
    global temperature_water_table
    global list_of_valves
    global watering_radius
    global latitude
    global longitude
    global username
    global password
    global api_key
    global min_soil_moisture
    global min_frequency_days
    global min_watering_time

    config = configparser.ConfigParser()
    config.read('config.ini')

    mode = config['DEFAULT']['MODE']

    min_watering_time = float(config['DEFAULT']['MIN_WATERING_TIME'])
    if min_watering_time == '':
        min_watering_time = 100000

    temperature_water_table = [
        (5, config['DEFAULT']['WATER_NEED_AT_5_C']),
        (10, config['DEFAULT']['WATER_NEED_AT_10_C']),
        (15, config['DEFAULT']['WATER_NEED_AT_15_C']),
        (20, config['DEFAULT']['WATER_NEED_AT_20_C']),
        (25, config['DEFAULT']['WATER_NEED_AT_25_C']),
        (30, config['DEFAULT']['WATER_NEED_AT_30_C']),
        (35, config['DEFAULT']['WATER_NEED_AT_35_C']),
        (40, config['DEFAULT']['WATER_NEED_AT_40_C'])
    ]

    temperature_water_table = list(filter(lambda t: '' not in t, temperature_water_table))

    for i in range(len(temperature_water_table)):
        temperature_water_table[i] = list(temperature_water_table[i])
        temperature_water_table[i][1] = float(temperature_water_table[i][1])
        temperature_water_table[i] = tuple(temperature_water_table[i])

    list_of_valves = {
        'valve1': {
            'nozzle_number': config['DEFAULT']['VALVE1_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE1_RADIUS']
        },
        'valve2': {
            'nozzle_number': config['DEFAULT']['VALVE2_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE2_RADIUS']
        },
        'valve3': {
            'nozzle_number': config['DEFAULT']['VALVE3_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE3_RADIUS']
        },
        'valve4': {
            'nozzle_number': config['DEFAULT']['VALVE4_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE4_RADIUS']
        },
        'valve5': {
            'nozzle_number': config['DEFAULT']['VALVE5_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE5_RADIUS']
        },
        'valve6': {
            'nozzle_number': config['DEFAULT']['VALVE6_NOZZLE'],
            'irrigation_radius': config['DEFAULT']['VALVE6_RADIUS']
        }
    }

    for valve in list(list_of_valves.keys()):
        if (list_of_valves.get(valve).get('nozzle_number') is ''):
            del list_of_valves[valve]

    watering_radius = float(config['DEFAULT']['WATERING_RADIUS'])

    min_soil_moisture = int(config['DEFAULT']['SOIL_MOISTURE_THREASHOLD'])

    min_frequency_days = int(config['DEFAULT']['MIN_FREQUENCY_DAYS'])

    latitude = config['DEFAULT']['LATITUDE']
    longitude = config['DEFAULT']['LONGITUDE']

    username = config['DEFAULT']['GARDENA_USERNAME']
    password = config['DEFAULT']['GARDENA_PASSWORD']

    api_key = config['DEFAULT']['API_KEY']


def linear_fit(table):
    x = np.array([x[0] for x in table])
    y = np.array([y[1] for y in table])
    model = np.polyfit(x, y, 1)
    fit = np.poly1d(model)
    return fit


# R-squared minimieren mit fit

def circle_area(radius, degree):
    area = radius ** 2 * math.pi * degree / 360
    return area


def extract_rain_from_dict(i, json_data):
    try:
        output = json_data.get('list')[i].get('rain').get('3h')
    except AttributeError:
        output = 0
    if output is None:
        output = 0
    return output


def get_weather_forecast(latitude, longitude, api_key):
    response = requests.get(
        'http://api.openweathermap.org/data/2.5/forecast?lat={}&lon={}&APPID={}'.format(latitude, longitude, api_key))

    json_data = json.loads(response.text)

    weather_forecast = pd.DataFrame(columns=['date', 'temperature_in_c', 'precipitation_in_mm'])

    for i in range(len(json_data.get('list'))):
        weather_forecast.loc[i, 'date'] = (datetime.datetime.fromtimestamp(json_data.get('list')[i].get('dt')))
        weather_forecast.loc[i, 'temperature_in_c'] = json_data.get('list')[i].get('main').get('temp_max') - 273.15
        weather_forecast.loc[i, 'precipitation_in_mm'] = extract_rain_from_dict(i, json_data)
    weather_forecast['temperature_in_c'] = pd.to_numeric(weather_forecast['temperature_in_c'])
    weather_forecast['precipitation_in_mm'] = pd.to_numeric(weather_forecast['precipitation_in_mm'])
    for i in range(len(weather_forecast['date'])):
        weather_forecast.loc[i, 'date'] = pd.Timestamp(weather_forecast['date'][i])
    return weather_forecast


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


def get_device_id_for_Irrigation_Control(token, location_id):
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
        if json_data.get('devices')[i].get('name') == 'Irrigation Control':
            output = json_data.get('devices')[i].get('id')

    return output


def send_watering_command_to_valve(time_in_min, valve_id):
    global token
    global location_id
    global device_id
    headers = {
        'authorization': 'Bearer {token}'.format(token=token),
        'authorization-provider': 'husqvarna',
    }

    params = (
        ('locationId', location_id),
    )

    data = '{{"properties":{{"name":"watering_timer_{id}","value":{{"state":"manual","duration":{t},"valve_id":{id}}}}}}}'.format(
        t=time_in_min, id=valve_id)

    requests.put(
        'https://smart.gardena.com/v1/devices/{}/abilities/watering/properties/watering_timer_{}'.format(device_id,
                                                                                                         valve_id),
        headers=headers, params=params, data=data)


def initialize_watering():
    location_id = get_location_id(token, user_id)
    device_id = get_device_id_for_Irrigation_Control(token, location_id)
    return location_id, device_id


def add_lph_to_valve_dict(list_of_valves):
    liter_per_hour_nozzle = {
        'nozzle1': 370,
        'nozzle2': 500,
        'nozzle3': 650,
        'nozzle4': 820
    }

    for valve in list_of_valves.keys():
        lph = liter_per_hour_nozzle['nozzle' + str(list_of_valves.get(valve).get('nozzle_number'))]
        list_of_valves.get(valve).update({'litres_per_hour': '{}'.format(lph)})


def calculate_irrigation_area_per_valve(list_of_valves, watering_radius):
    for element in list_of_valves:
        degree = float(list_of_valves.get(element).get('irrigation_radius'))
        area = circle_area(watering_radius, degree)
        list_of_valves.get(element).update({'area_covered': '{}'.format(area)})


def get_weather_history():
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute('''SELECT DATE(DATE) AS date,
            AVG(temperature_in_c),
            SUM(precipitation_in_mm)
     FROM   weather
     GROUP BY DATE(DATE)
     ORDER BY DATE DESC limit 3''')

    weather_history = pd.DataFrame(c.fetchall())
    weather_history.columns = ['date', 'temperature_in_c', 'precipitation_in_mm']
    weather_history['date'] = pd.to_datetime(weather_history['date'])
    weather_history = weather_history.sort_values(by='date')
    weather_history = weather_history.reset_index(drop=True)
    conn.close()
    return weather_history


def calculate_water_needs(temperature_in_c, precipitation):
    global fit
    need = fit(temperature_in_c)
    if need <= 0:
        need = 0
    need = need - precipitation
    return need


def add_water_needs_column(df):
    df['water_need'] = 0
    for i in df.index:
        df.loc[i, 'water_need'] = calculate_water_needs(df['temperature_in_c'][i], df['precipitation_in_mm'][i])


def write_token_to_txt(username, password):
    token, user_id = get_gardena_token_user_id(username, password)
    with open('token+user_id.txt', 'w') as f:
        f.write(token+','+user_id)
    return token, user_id
        

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
        token, user_id = write_token_to_txt(username, password)
    response = get_response_code(token, user_id)  
    if response.status_code == 403:
        token, user_id = write_token_to_txt(username, password)
    return token, user_id



initialize_program()

if mode == 'MANUAL':
    sys.exit("Mode is set to MANUAL")
    
token, user_id = token_handling(username, password)

location_id, device_id = initialize_watering()

add_lph_to_valve_dict(list_of_valves)

weather_forecast = get_weather_forecast(latitude, longitude, api_key)

weather_history = get_weather_history()
weather_history.index = weather_history['date']
weather_history = weather_history.drop('date', axis=1)

weather_forecast.index = weather_forecast['date']
weather_forecast = weather_forecast.resample('D').agg({'temperature_in_c': 'mean', 'precipitation_in_mm': 'sum'})

fit = linear_fit(temperature_water_table)

add_water_needs_column(weather_forecast)
add_water_needs_column(weather_history)
calculate_irrigation_area_per_valve(list_of_valves, watering_radius)

weather_forecast['date'] = weather_forecast.index
weather_history['date'] = weather_history.index

# Depending on time of day, decide which forecast observation is relevant
# E.g. if the script runs in the evening, the forecast for today is not relevant for our system but instead the observation tomorrow
# If we're watering in the morning, it matters if it's going to rain today
if datetime.datetime.now().time() > datetime.time(12):
    forecast_date = (
                datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1))
else:
    forecast_date = (datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))

# Get the sum of rain_in_mm for the forecast date specified
forecasted_value = weather_forecast[weather_forecast['date'] == forecast_date]['water_need'].values[0]

# Similar like before, decide which history date is relevant to make watering predictions
if datetime.datetime.now().time() < datetime.time(12):
    history_date = (
                datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1))
else:
    history_date = (datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))

# Check when the last irrigation occured (if None, choose today-7days, if table doesnt exist-> create it)
try:
    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    c.execute('''SELECT DATE FROM irrigation
     ORDER BY DATE DESC limit 1''')

    if list(c) == []:
        last_watering_date = (
                    datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(
                days=7))

    c.execute('''SELECT DATE FROM irrigation
     ORDER BY DATE DESC limit 1''')

    time_last_record = c.execute('SELECT DATE FROM irrigation ORDER BY DATE DESC limit 1').fetchone()[0]
    time_last_record = datetime.datetime.strptime(time_last_record, '%Y-%m-%d %H:%M:%S')
    if time_last_record.time() < datetime.time(12):
        last_watering_date = (
                    time_last_record.replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=1))
    else:
        last_watering_date = (time_last_record.replace(hour=0, minute=0, second=0, microsecond=0))
except sqlite3.OperationalError:
    last_watering_date = (
                datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=7))

weather_history_subset = weather_history[weather_history['date'] > last_watering_date]

total_water_need = sum(weather_history_subset['water_need'].values)


watering_times_per_valve = []

for valve in list_of_valves:
    watering_times_per_valve.append(float(list_of_valves.get(valve).get('area_covered')) * total_water_need)

total_watering_time = int(sum(watering_times_per_valve))


watering_decision = 'yes'

if forecasted_value <= -3:
    watering_decision = 'forecasted value too high'

conn = sqlite3.connect('weather.db')
c = conn.cursor()
soil_moisture = c.execute('''SELECT soil_mositure_in_p FROM sensor ORDER BY DATE DESC limit 1''').fetchone()[0]

if soil_moisture > min_soil_moisture:
    watering_decision = 'min soil temperature not reached'

if last_watering_date < datetime.datetime.now() - datetime.timedelta(days=min_frequency_days):
    watering_decision = 'time since last watering not long enough'

if total_watering_time < min_watering_time:
    watering_decision = 'not exceeding min watering time'

if watering_decision != 'yes':
    sys.exit("Conditions for watering not met: {}".format(watering_decision))


conn = sqlite3.connect('weather.db')
c = conn.cursor()
try:
    c.execute('''CREATE TABLE irrigation
                     (date timestamp , irrigation_in_mm numeric, total_watring_time_min numeric)''')
except sqlite3.OperationalError:
    pass
c.execute("INSERT INTO irrigation VALUES (?, ?, ?)", (datetime.datetime.now().replace(microsecond=0), total_water_need, total_watering_time))
conn.commit()
conn.close()

# make a pre-soak of the grass (5min per zone so more water can enter the soil during watering)
if watering_times_per_valve[0] < 5:
    sys.exit("Watering times too short")

for i, j in enumerate(watering_times_per_valve):
    watering_times_per_valve[i] -= 5

for i in range(len(watering_times_per_valve)):
    valve_id = i + 1
    send_watering_command_to_valve(5, valve_id)
    wait_time.sleep(5 * 60 + 1)

if watering_times_per_valve[0] < 5:
    sys.exit("Watering times too short")

# since the Gardena interface only allows for watering times between 0-59, we have to split the watering sessions into multiple pieces
for i, element in enumerate(watering_times_per_valve):
    valve_id = i + 1
    time = int(element)
    if time > 59:
        cycles = time // 59 + 1
        for i in range(cycles):
            if (time - 59) > 0:
                time -= 59
                send_watering_command_to_valve(59, valve_id)
                wait_time.sleep(59 * 60 + 1)
            else:
                send_watering_command_to_valve(time, valve_id)
                wait_time.sleep(time * 60 + 1)
    else:
        send_watering_command_to_valve(time, valve_id)
        wait_time.sleep(element * 60 + 1)
