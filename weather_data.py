import inspect
import json
import os
import sqlite3
from datetime import datetime
from urllib.request import urlopen


def get_weather_data_for_location(location_id, url):
    response = urlopen(url).read().decode("utf-8")
    response_dict = json.loads(response)

    creation_time = datetime.strptime(response_dict['creation_time'], '%d.%m.%Y %H:%M')

    for idx, element in enumerate(response_dict['features']):
        if element['id'] == location_id:
            return response_dict['features'][idx]['properties']['value'], creation_time


def get_precipitation_for_location(location_id):
    url = 'https://data.geo.admin.ch/ch.meteoschweiz.messwerte-niederschlag-10min/ch.meteoschweiz.messwerte-niederschlag-10min_en.json'
    return get_weather_data_for_location(location_id, url)


def get_temperature_for_location(location_id):
    url = 'https://data.geo.admin.ch/ch.meteoschweiz.messwerte-lufttemperatur-10min/ch.meteoschweiz.messwerte-lufttemperatur-10min_en.json'
    return get_weather_data_for_location(location_id, url)


def get_wind_for_location(location_id):
    url = 'https://data.geo.admin.ch/ch.meteoschweiz.messwerte-windgeschwindigkeit-kmh-10min/ch.meteoschweiz.messwerte-windgeschwindigkeit-kmh-10min_en.json'
    return get_weather_data_for_location(location_id, url)


def get_radiation_for_location(location_id):
    url = 'https://data.geo.admin.ch/ch.meteoschweiz.messwerte-globalstrahlung-10min/ch.meteoschweiz.messwerte-globalstrahlung-10min_en.json'
    return get_weather_data_for_location(location_id, url)


def weatherdata_to_db():
    precipitation, creation_time = get_precipitation_for_location('BAS')
    temperature, creation_time = get_temperature_for_location('BAS')
    wind, creation_time = get_wind_for_location('BAS')
    radiation, creation_time = get_radiation_for_location('BAS')

    if (precipitation == 9999) or (temperature == 9999) or (wind == 9999) or (radiation == 9999):
        sys.exit('API values are 9999 --> did not write to db')

    conn = sqlite3.connect('weather.db')
    c = conn.cursor()
    try:
        c.execute('''CREATE TABLE weather
                         (date timestamp , temperature_in_c numeric, precipitation_in_mm numeric, wind_in_kmh numeric, radiation_in_W_m2 numeric)''')
    except sqlite3.OperationalError:
        pass
    c.execute("INSERT INTO weather VALUES (?, ?, ?, ?, ?)",
              (creation_time, temperature, precipitation, wind, radiation))
    conn.commit()
    conn.close()


def set_script_folder_path():
    filename = inspect.getframeinfo(inspect.currentframe()).filename
    path = os.path.dirname(os.path.abspath(filename))
    os.chdir(path)


set_script_folder_path()
weatherdata_to_db()
