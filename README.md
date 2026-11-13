# JUNG HOME for Home Assistant

[![Open in Marketplace](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=mariusbiller&repository=ha-junghome&category=integration)

Control your JUNG HOME devices from Home Assistant through the JUNG HOME Gateway.

Communication stays on your local network — no cloud required.

## Supported devices

| Device | Features |
| --- | --- |
| On/off light | Switching |
| Dimmable light | Switching and brightness |
| Tunable white light | Switching and brightness only; no color temperature control |
| Socket | Switching and power measurement |
| Window cover | Cover control |
| Rocker switch | Press and release events for each direction; status LED control |
| Room thermostat | Current and target temperature; Frost, Eco, and Comfort presets |
| Gateway | Registered as a hub device |

Rocker switch events let you build automations for taps and holds, such as hold-to-dim.

## Features

- Device states update automatically as changes happen.
- The integration reconnects automatically if the connection to the Gateway is interrupted.
- New devices are added automatically, and entities for removed devices are removed when the Gateway sends an updated device list.
- Group names are imported from JUNG HOME and associated with the corresponding devices.
- Devices are automatically assigned to Home Assistant areas based on their JUNG HOME groups.




## Before you start

- Set up your JUNG HOME devices and Gateway in the official JUNG HOME app.
- Keep the Gateway powered on and on the same local network as Home Assistant. Automatic discovery requires the same network subnet.
- Give the Gateway a stable IP address, for example with a DHCP reservation in your router.

## Installation
> Requires Home Assistant **2026.11 or newer**.

Use the **Open in Marketplace** badge at the top of this page, add the repository if prompted, and install **JUNG HOME**. Then restart Home Assistant.

To add the repository yourself:

1. Open Home Assistant and go to **Settings > Marketplace**.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Enter `https://github.com/mariusbiller/ha-junghome`.
4. Select the category **Integration**.
5. Search for **JUNG HOME** in Marketplace and install the integration.
6. Restart Home Assistant.


## Setup
1. In Home Assistant, go to **Settings > Devices & services** and click **Add Integration**.
2. Search for **JUNG HOME** and start the setup flow.
3. Enter your JUNG HOME Gateway's IP address. If Home Assistant has discovered the gateway automatically, confirm the suggested IP address.
4. Press the button on your JUNG HOME Gateway when the flow asks you to allow Home Assistant access. The integration will request the access token automatically.
5. If automatic token registration fails, enter the authentication token manually in the next step.

**Hints**
- *Make sure your JUNG HOME Gateway's IP address does not change, for example by creating a DHCP reservation in your router.*
- *For proper discovery, make sure your JUNG HOME Gateway and your Home Assistant instance are in the same network subnet.*

## Credits

- Special thanks to [@luismalves](https://github.com/luismalves) for bringing the integration to the next level.
- Special thanks to [@kkellermann](https://github.com/kkellermann) for integrating the socket measuring sensor function.
- Special thanks to [@micthon](https://github.com/micthon) for adding room thermostat support.

## Disclaimer

This project is a privately developed open-source integration for the JUNG HOME smart home system provided by Albrecht Jung GmbH & Co. KG. I have not been commissioned or authorized by them to create this integration.

This project is offered as is, without any guarantee or warranty of any kind. I do not assume any responsibility for any issues, damages, or losses that may arise from the use of this integration.
Users are encouraged to review and understand the terms and conditions of Albrecht Jung GmbH & Co. KG's services before using this integration.

Contributions and feedback are welcome.
