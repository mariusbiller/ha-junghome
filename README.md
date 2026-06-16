# ha-junghome
This project integrates JUNG HOME devices into Home Assistant.
Communication with JUNG HOME devices uses the local network via the JUNG HOME Gateway - no cloud required.

## Supported device types
- On/Off Light
- Dimmable Light
- Tunable White Light (switching and brightness only)
- Socket (including power measurement)
- Window Cover
- Rocker Switch (button press entities can be used in automations to react to physical button presses)
- Gateway as Hub device


## Prerequisites
- JUNG HOME devices have already been installed and set up using the official JUNG HOME app.
- A JUNG HOME Gateway has been added, is active, and is on the same local network as your Home Assistant instance.
- Make sure your JUNG HOME Gateway's IP address does not change, for example by creating a DHCP reservation in your router.


## Installation
### Option 1: Manual Installation
1. Copy this folder to `<config_dir>/custom_components/junghome/`
2. Restart Home Assistant.

### Option 2: Install via HACS
> *If you have not installed HACS (Home Assistant Community Store) yet, follow the official guide: [HACS Installation Guide](https://hacs.xyz/docs/use/download/download/)*

1. Open Home Assistant and go to **HACS > Integrations**.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Add the URL of this GitHub repository: `https://github.com/mariusbiller/ha-junghome`.
4. Select the category **Integration**.
5. Search for **JUNG HOME** in HACS and install the integration.
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

## Disclaimer
This project is a privately developed open-source integration for the JUNG HOME smart home system provided by Albrecht Jung GmbH & Co. KG. I have not been commissioned or authorized by them to create this integration.

This project is offered as is, without any guarantee or warranty of any kind. I do not assume any responsibility for any issues, damages, or losses that may arise from the use of this integration.
Users are encouraged to review and understand the terms and conditions of Albrecht Jung GmbH & Co. KG's services before using this integration.

Contributions and feedback from the community are welcome and appreciated, but please keep the limitations and disclaimers stated here in mind.

Thank you.
