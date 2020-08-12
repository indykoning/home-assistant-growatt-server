# Home Assistant Growatt server integration
**I am not actively maintaining this anymore, most (if not all) features are already available in the latest Home Assistant version.**

This is a sensor to collect information from your growatt inverters using growatt server.

This will log into your growatt account and grab the first "Plant" after which it collects the inverters on this plant and creates sensors for these inverters as well as a total sensor.

In case of two inverters this will create 3 sensors. One for inverter 1, one for inverter 2 and one for the total of these. The state of these sensors all contain the current power delivered to the net in `W`. There is a lot more information available in the attributes of the inverter sensors like individual power of the different inputs of the inverters (if applicable, otherwise it'll return 0)


## Installation
Place the contents of this repo
in `<config directory>/custom_components/growatt/`.

Once this is done you can move on to configuring it.
```
sensor:
  - platform: growatt
    username: <growatt server username>
    password: <growatt server password>
```

That was the basic set up, if you have multiple plants you could add them by adding another platform.

```
sensor:
  - platform: growatt
    name: <name for the inverters added>
    plant_id: <the id of this plant>
    username: <growatt server username>
    password: <growatt server password>
  - platform: growatt
    name: <name for the inverters added>
    plant_id: <the id of this plant>
    username: <growatt server username>
    password: <growatt server password>
```

The api endpoints were discovered by reverse engineering the growatt app, these may change in the future.
