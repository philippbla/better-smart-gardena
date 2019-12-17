#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun  1 20:28:10 2019

@author: philipp
"""

import datetime
import json

import pandas as pd
import requests


def get_weather_forecast(consumer_key, consumer_secret, latitude, longitude):
    # Request Access token
    params = (
        ('grant_type', 'client_credentials'),
    )

    data = {
        'client_id': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
        'client_secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    }

    response = requests.post('https://api.srgssr.ch/oauth/v1/accesstoken', params=params, data=data)

    json_data = json.loads(response.text)
    access_token = json_data.get('access_token')

    # Request Weather Forecast
    headers = {
        'Authorization': 'Bearer {token}'.format(token=access_token),
    }

    params = (
        ('latitude', '40.000000'),
        ('longitude', '7.000000'),
    )

    response = requests.get('https://api.srgssr.ch/forecasts/v1.0/weather/7day', headers=headers, params=params)
    json_data = json.loads(response.text)

    now = datetime.datetime.now()
    datelist = []
    if now.time() >= datetime.time(12):
        relevant_date = (datetime.datetime.now() + datetime.timedelta(days=1)).date()
        for i in range(6):
            datelist.append(relevant_date + datetime.timedelta(days=i))
    else:
        relevant_date = datetime.datetime.now().date()
        for i in range(7):
            datelist.append(relevant_date + datetime.timedelta(days=i))

    for i, element in enumerate(datelist):
        datelist[i] = str(element)

    weather_forecast = list(filter(lambda d: d['date'] in datelist, json_data.get('7days')))

    temperature_forecast = []
    for i in range(len(weather_forecast)):
        values = weather_forecast[i].get('values')
        for value in values:
            for element in value.keys():
                if element == 'ttx':
                    temperature_forecast.append(float(value[element]))

    precipitation_forecast = []
    for i in range(len(weather_forecast)):
        values = weather_forecast[i].get('values')
        keys = []
        [keys.append(list(values[j].keys())[0]) for j in range(len(values))]
        if 'rsd' not in keys:
            precipitation_forecast.append(int(0))
            pass
        for value in values:
            for element in value.keys():
                if element == 'rsd':
                    precipitation_forecast.append(float(value[element]))

    datelist = pd.DataFrame(datelist)
    temperature_forecast = pd.DataFrame(temperature_forecast)
    precipitation_forecast = pd.DataFrame(precipitation_forecast)

    weather_forecast = pd.concat([datelist, temperature_forecast], axis=1, ignore_index=True)
    weather_forecast = pd.concat([weather_forecast, precipitation_forecast], axis=1, ignore_index=True)
    weather_forecast.columns = ['date', 'temperature_in_c', 'precipitation_in_mm']

    return weather_forecast


get_weather_forecast('xxxxxxxxxxxxxxxxx', 'xxxxxxxxxxxxxxx', '40.0000000000', '7.000000000')
