"""
Copyright 2018 Sjoerd Langkemper, Anil Roy and Indy Koning
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
"""Read status of growatt inverters."""
import datetime
import json
import logging
import re

import growattServer
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    ENERGY_KILO_WATT_HOUR,
    POWER_WATT,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_PLANT_ID = "plant_id"
DEFAULT_PLANT_ID = "0"
DEFAULT_NAME = "Growatt"
SCAN_INTERVAL = datetime.timedelta(minutes=5)

# Sensor type order is: Sensor name, Unit of measurement, api data name, additional options

TOTAL_SENSOR_TYPES = {
    "total_money_today": ("Total money today", "€", "plantMoneyText", {}),
    "total_money_total": ("Money lifetime", "€", "totalMoneyText", {}),
    "total_energy_today": (
        "Energy Today",
        ENERGY_KILO_WATT_HOUR,
        "todayEnergy",
        {"device_class": "power"},
    ),
    "total_output_power": (
        "Output Power",
        POWER_WATT,
        "invTodayPpv",
        {"device_class": "power"},
    ),
    "total_energy_output": (
        "Lifetime energy output",
        ENERGY_KILO_WATT_HOUR,
        "totalEnergy",
        {"device_class": "power"},
    ),
    "total_maximum_output": (
        "Maximum power",
        POWER_WATT,
        "nominalPower",
        {"device_class": "power"},
    ),
}

INVERTER_SENSOR_TYPES = {
    "inverter_energy_today": (
        "Energy today",
        ENERGY_KILO_WATT_HOUR,
        "powerToday",
        {"device_class": "power", "round": 1},
    ),
    "inverter_energy_total": (
        "Lifetime energy output",
        ENERGY_KILO_WATT_HOUR,
        "powerTotal",
        {"device_class": "power", "round": 1},
    ),
    "inverter_voltage_input_1": ("Input 1 voltage", "V","vpv1", {"round": 2}),
    "inverter_amperage_input_1": ("Input 1 Amperage", "A", "ipv1", {"round": 1}),
    "inverter_wattage_input_1": (
        "Input 1 Wattage",
        POWER_WATT,
        "ppv1",
        {"device_class": "power", "round": 1},
    ),
    "inverter_voltage_input_2": ("Input 2 voltage", "V","vpv2", {"round": 1}),
    "inverter_amperage_input_2": ("Input 2 Amperage", "A", "ipv2", {"round": 1}),
    "inverter_wattage_input_2": (
        "Input 2 Wattage",
        POWER_WATT,
        "ppv2",
        {"device_class": "power", "round": 1},
    ),
    "inverter_voltage_input_3": ("Input 3 voltage", "V","vpv3", {"round": 1}),
    "inverter_amperage_input_3": ("Input 3 Amperage", "A", "ipv3", {"round": 1}),
    "inverter_wattage_input_3": (
        "Input 3 Wattage",
        POWER_WATT,
        "ppv3",
        {"device_class": "power", "round": 1},
    ),
    "inverter_internal_wattage": (
        "Internal wattage",
        POWER_WATT,
        "ppv",
        {"device_class": "power", "round": 1},
    ),
    "inverter_reactive_voltage": ("Reactive voltage", "V","vacr", {"round": 1}),
    "inverter_inverter_reactive_amperage": ("Reactive amperage", "A", "iacr", {"round": 1}),
    "inverter_frequency": ("AC frequency", "Hz", "fac", {"round": 1}),
    "inverter_current_wattage": (
        "Output power",
        POWER_WATT,
        "pac",
        {"device_class": "power", "round": 1},
    ),
    "inverter_current_reactive_wattage": (
        "Reactive wattage",
        POWER_WATT,
        "pacr",
        {"device_class": "power", "round": 1},
    ),
    "inverter_ipm_temperature": (
        "Intelligent Power Management temperature",
        TEMP_CELSIUS,
        "ipmTemperature",
        {"device_class": "temperature", "round": 1},
    ),
    "inverter_temperature": (
        "Temperature",
        TEMP_CELSIUS,
        "temperature",
        {"device_class": "temperature", "round": 1},
    ),
}

STORAGE_SENSOR_TYPES = {
    "storage_storage_production_today": (
        "Storage production today",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeToday",
        {"device_class": "power"},
    ),
    "storage_storage_production_lifetime": (
        "Lifetime Storage production",
        ENERGY_KILO_WATT_HOUR,
        "eBatDisChargeTotal",
        {"device_class": "power"},
    ),
    "storage_grid_discharge_today": (
        "Grid discharged today",
        ENERGY_KILO_WATT_HOUR,
        "eacDisChargeToday",
        {"device_class": "power"},
    ),
    "storage_load_consumption_today": (
        "Load consumption today",
        ENERGY_KILO_WATT_HOUR,
        "eopDischrToday",
        {"device_class": "power"},
    ),
    "storage_load_consumption_lifetime": (
        "Lifetime load consumption",
        ENERGY_KILO_WATT_HOUR,
        "eopDischrTotal",
        {"device_class": "power"},
    ),
    "storage_grid_charged_today": (
        "Grid charged today",
        ENERGY_KILO_WATT_HOUR,
        "eacChargeToday",
        {"device_class": "power"},
    ),
    "storage_charge_storage_lifetime": (
        "Lifetime storaged charged",
        ENERGY_KILO_WATT_HOUR,
        "eChargeTotal",
        {"device_class": "power"},
    ),
    "storage_solar_production": (
        "Solar power production",
        POWER_WATT,
        "ppv",
        {"device_class": "power"},
    ),
    "storage_battery_percentage": (
        "Battery percentage",
        "%",
        "capacity",
        {"device_class": "battery"},
    ),
    "storage_power_flow": (
        "Storage charging/ discharging(-ve)",
        POWER_WATT,
        "pCharge",
        {"device_class": "power"},
    ),
    "storage_load_consumption_solar_storage": (
        "Load consumption(Solar + Storage)",
        "VA",
        "rateVA",
        {},
    ),
    "storage_charge_today": (
        "Charge today",
        ENERGY_KILO_WATT_HOUR,
        "eChargeToday",
        {"device_class": "power"},
    ),
    "storage_import_from_grid": (
        "Import from grid",
        POWER_WATT,
        "pAcInPut",
        {"device_class": "power"},
    ),
    "storage_import_from_grid_today": (
        "Import from grid today",
        ENERGY_KILO_WATT_HOUR,
        "eToUserToday",
        {"device_class": "power"},
    ),
    "storage_import_from_grid_total": (
        "Import from grid total",
        ENERGY_KILO_WATT_HOUR,
        "eToUserTotal",
        {"device_class": "power"},
    ),
    "storage_load_consumption": (
        "Load consumption",
        POWER_WATT,
        "outPutPower",
        {"device_class": "power"},
    ),
    "storage_grid_voltage": ("AC input voltage", "V","vGrid", {"round": 2}),
    "storage_pv_charging_voltage": ("PV charging voltage", "V","vpv", {"round": 2}),
    "storage_ac_input_frequency_out": (
        "AC input frequency",
        "Hz",
        "freqOutPut",
        {"round": 2},
    ),
    "storage_output_voltage": ("Output voltage", "V","outPutVolt", {"round": 2}),
    "storage_ac_output_frequency": (
        "Ac output frequency",
        "Hz",
        "freqGrid",
        {"round": 2},
    ),
    "storage_current_PV": ("Solar charge current", "A", "iAcCharge", {"round": 2}),
    "storage_current_1": ("Solar current to storage", "A", "iChargePV1", {"round": 2}),
    "storage_grid_amperage_input": (
        "Grid charge current",
        "A",
        "chgCurr",
        {"round": 2},
    ),
    "storage_grid_out_current": (
        "Grid out current",
        "A",
        "outPutCurrent",
        {"round": 2},
    ),
    "storage_battery_voltage": ("Battery voltage", "V","vBat", {"round": 2}),
    "storage_load_percentage": (
        "Load percentage",
        "%",
        "loadPercent",
        {"device_class": "battery", "round": 2},
    ),
}

SENSOR_TYPES = {**TOTAL_SENSOR_TYPES, **INVERTER_SENSOR_TYPES, **STORAGE_SENSOR_TYPES}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PLANT_ID, default=DEFAULT_PLANT_ID): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Growatt sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    plant_id = config[CONF_PLANT_ID]
    name = config[CONF_NAME]

    api = growattServer.GrowattApi()

    # Log in to api and fetch first plant if no plant id is defined.
    login_response = api.login(username, password)
    if not login_response["success"] and login_response["errCode"] == "102":
        _LOGGER.error("Username or Password may be incorrect!")
        return
    user_id = login_response["userId"]
    if plant_id == DEFAULT_PLANT_ID:
        plant_info = api.plant_list(user_id)
        plant_id = plant_info["data"][0]["plantId"]

    # Get a list of devices for specified plant to add sensors for.
    devices = api.device_list(plant_id)
    entities = []
    probe = GrowattData(api, username, password, plant_id, "total")
    for sensor in TOTAL_SENSOR_TYPES:
        entities.append(
            GrowattInverter(probe, f"{name} Total", sensor, f"{plant_id}-{sensor}")
        )

    # Add sensors for each device in the specified plant.
    for device in devices:
        probe = GrowattData(
            api, username, password, device["deviceSn"], device["deviceType"]
        )
        sensors = []
        if device["deviceType"] == "inverter":
            sensors = INVERTER_SENSOR_TYPES
        elif device["deviceType"] == "storage":
            probe.plant_id = plant_id
            sensors = STORAGE_SENSOR_TYPES

        for sensor in sensors:
            entities.append(
                GrowattInverter(
                    probe,
                    f"{device['deviceAilas']}",
                    sensor,
                    f"{device['deviceSn']}-{sensor}",
                )
            )

    add_entities(entities, True)


class GrowattInverter(Entity):
    """Representation of a Growatt Sensor."""

    def __init__(self, probe, name, sensor, unique_id):
        """Initialize a PVOutput sensor."""
        self.sensor = sensor
        self.probe = probe
        self._name = name
        self._state = None
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._name} {SENSOR_TYPES[self.sensor][0]}"

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return self._unique_id

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:solar-power"

    @property
    def state(self):
        """Return the state of the sensor."""
        result = self.probe.get_data(SENSOR_TYPES[self.sensor][2])
        round_to = SENSOR_TYPES[self.sensor][3].get("round", None)
        if round_to is not None:
            result = round(result, round_to)
        return result

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SENSOR_TYPES[self.sensor][3].get("device_class", None)

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self.sensor][1]

    def update(self):
        """Get the latest data from the Growat API and updates the state."""
        self.probe.update()


class GrowattData:
    """The class for handling data retrieval."""

    def __init__(self, api, username, password, device_id, growatt_type):
        """Initialize the probe."""

        self.growatt_type = growatt_type
        self.api = api
        self.device_id = device_id
        self.plant_id = None
        self.data = {}
        self.username = username
        self.password = password

    def inverter_detail(self, inverter_id):
        """
        Get "All parameters" from PV inverter.
        """
        response = self.api.session.get(self.api.get_url('newInverterAPI.do'), params={
            'op': 'getInverterDetailData',
            'inverterId': inverter_id
        })

        data = json.loads(response.content.decode('utf-8'))
        return data

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update probe data."""
        self.api.login(self.username, self.password)
        _LOGGER.debug("Updating data for %s", self.device_id)
        try:
            if self.growatt_type == "total":
                total_info = self.api.plant_info(self.device_id)
                del total_info["deviceList"]
                # PlantMoneyText comes in as "3.1/€" remove anything that isn't part of the number
                total_info["plantMoneyText"] = re.sub(
                    r"[^\d.,]", "", total_info["plantMoneyText"]
                )
                self.data = total_info
            elif self.growatt_type == "inverter":
                inverter_info = self.inverter_detail(self.device_id)
                self.data = inverter_info
            elif self.growatt_type == "storage":
                storage_info_detail = self.api.storage_params(self.device_id)[
                    "storageDetailBean"
                ]
                storage_energy_overview = self.api.storage_energy_overview(
                    self.plant_id, self.device_id
                )
                self.data = {**storage_info_detail, **storage_energy_overview}
        except json.decoder.JSONDecodeError:
            _LOGGER.error("Unable to fetch data from Growatt server")

    def get_data(self, variable):
        """Get the data."""
        return self.data.get(variable)
