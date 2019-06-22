"""
Support for Growatt Invertor using API Library from https://github.com/Sjord/growatt_api_client thanks to Sjoerd Langkemper(https://github.com/Sjord)
Copyright 2018 Sjoerd Langkemper, Anil Roy and Indy Koning
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import logging
import voluptuous as vol
from collections import namedtuple
from enum import IntEnum
import datetime
import hashlib
import json
import requests
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_TEMPERATURE, CONF_API_KEY, CONF_NAME, ATTR_DATE, ATTR_TIME,
    ATTR_VOLTAGE)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity


"""Start the logger"""
_LOGGER = logging.getLogger(__name__)

plant_id = 0
"""configuration for accessing the Unifi Controller"""
CONF_USERNAME = 'username'
CONF_PASSWORD = 'password'
CONF_PLANT_ID = 'plant_id'
DEFAULT_UNIT = 'kW'
DEFAULT_NAME = 'Growatt'
SCAN_INTERVAL = datetime.timedelta(minutes=5)

"""Define the schema for the Sensor Platform"""
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PLANT_ID, default='0'): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Growatt sensor."""
    """get all the parameters passed by the user to access the controller"""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    plant_id = config.get(CONF_PLANT_ID)
    name = config.get(CONF_NAME)

    api = GrowattApi()

    login_res = api.login(username, password)
    user_id = login_res['userId']
    if plant_id is '0':
        plant_info = api.plant_list(user_id)
        plant_id = plant_info['data'][0]['plantId']
        pass

    inverters = []
    try:
        inverters = api.inverter_list(plant_id)
    except APIError as ex:
        _LOGGER.error("Failed to connect to Growatt server: %s", ex)
        return False

    #_LOGGER.info("Growatt data is. {}".format(plant_info))
    #_LOGGER.info("Growatt detail is. {}".format(plant_detail    ))
    # the controller was loaded properly now get the user groups to find the one you want
    add_devices([GrowattInverter(api, name + '_Total', plant_id, username, password)], True)

    for inverter in inverters:
        _LOGGER.info("Growatt data for " + inverter['deviceAilas'] + " is: {}".format(inverter))
        add_devices([GrowattInverter(api, name + '_' + inverter['deviceAilas'], inverter['deviceSn'], username, password)], True)

class GrowattInverter(Entity):
    """Representation of a Growattt Sensor."""

    def __init__(self, api, name, inverter_id, u, p):
        """Initialize a PVOutput sensor."""
        self.api = api
        self._name = name
        self.inverter_id = inverter_id
        self.username = u
        self.password = p
        self.isTotal = 'Total' in name and inverter_id.isdigit()
        self._state = None
        self.attributes = {}
        self._unit_of_measurement = 'W'
        self.status = namedtuple(
            'status', [ATTR_DATE, ATTR_TIME,
                       ATTR_TEMPERATURE, ATTR_VOLTAGE])

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement


    @property
    def device_state_attributes(self):
        """Return the state attributes of the monitored installation."""
        attributes = self.attributes
        attributes['icon'] = 'mdi:solar-power'
        return attributes


    def update(self):
        """Get the latest data from the Growat API and updates the state."""
        try:
            login_res = self.api.login(self.username, self.password)
            if self.isTotal:
                total_info = self.api.plant_info(self.inverter_id)
                del total_info['deviceList']
                self._state = total_info['invTodayPpv']
                self.attributes = total_info
            else:
                inverter_info = self.api.inverter_detail(self.inverter_id)

                self.attributes = inverter_info['data']
                self._state = inverter_info['data']['pac']
        except TypeError:
            _LOGGER.error(
                "Unable to fetch data from Growatt server. %s")


'''
Copied directly from https://github.com/Sjord/growatt_api_client thanks to Sjoerd Langkemper(https://github.com/Sjord)
'''
def hash_password(password):
    """
    Normal MD5, except add c if a byte of the digest is less than 10.
    """
    password_md5 = hashlib.md5(password.encode('utf-8')).hexdigest()
    for i in range(0, len(password_md5), 2):
        if password_md5[i] == '0':
            password_md5 = password_md5[0:i] + 'c' + password_md5[i + 1:]
    return password_md5


class Timespan(IntEnum):
    day = 1
    month = 2


class GrowattApi:
    server_url = 'http://server.growatt.com/'

    def __init__(self):
        self.session = requests.Session()

    def get_url(self, page):
        return self.server_url + page

    def login(self, username, password):
        password_md5 = hash_password(password)
        response = self.session.post(self.get_url('LoginAPI.do'), data={
            'userName': username,
            'password': password_md5
        })
        data = json.loads(response.content.decode('utf-8'))
        return data['back']

    def plant_list(self, user_id):
        response = self.session.get(self.get_url('PlantListAPI.do'),
                                    params={'userId': user_id},
                                    allow_redirects=False)
        if response.status_code != 200:
            raise RuntimeError("Request failed: %s", response)
        data = json.loads(response.content.decode('utf-8'))
        return data['back']

    def plant_detail(self, plant_id, timespan, date):
        assert timespan in Timespan
        if timespan == Timespan.day:
            date_str = date.strftime('%Y-%m-%d')
        elif timespan == Timespan.month:
            date_str = date.strftime('%Y-%m')

        response = self.session.get(self.get_url('PlantDetailAPI.do'), params={
            'plantId': plant_id,
            'type': timespan.value,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))
        return data['back']

    def inverter_data(self, inverter_id, date):
        if date is None:
            date = datetime.date.today()
        date_str = date.strftime('%Y-%m-%d')
        response = self.session.get(self.get_url('newInverterAPI.do'), params={
            'op': 'getInverterData',
            'id': inverter_id,
            'type': 1,
            'date': date_str
        })
        data = json.loads(response.content.decode('utf-8'))
        return data

    def inverter_detail(self, inverter_id):
        response = self.session.get(self.get_url('newInverterAPI.do'), params={
            'op': 'getInverterDetailData_two',
            'inverterId': inverter_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    def inverter_list(self, plant_id):
        return self.plant_info(plant_id)['deviceList']

    def plant_info(self, plant_id):
        response = self.session.get(self.get_url('newPlantAPI.do'), params={
            'op': 'getAllDeviceListThree',
            'plantId': plant_id,
            'pageNum': 1,
            'pageSize': 1
        })
        data = json.loads(response.content.decode('utf-8'))
        return data
