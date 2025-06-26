# ha-junghome
This is a bare minimum example integration showing how to integrate JUNG HOME devices into Home Assistant.

The communication to JUNG HOME devices runs over local network via the JUNG HOME Gateway – no cloud required.

## Supported device types
- OnOff Light
- Dimmable Light
- Tuneable White Light (switching and brightness only)
- Socket (displayed as Light)
- Window Cover

>**hint:**
*Please note that the provided integration is a bare minimum example and may have limitations regarding its quality and functionality.*

## Prerequisites
- JUNG HOME devices have already been installed and set up using the official JUNG HOME App.
- A JUNG HOME Gateway is added, active, and in the same local network as your Home Assistant instance.


## Installation
### Option 1: Manual Installation
- Copy this folder to `<config_dir>/custom_components/junghome/`

### Option 2: Install via HACS
1. Open Home Assistant and go to **HACS > Integrations**.
2. Click the three dots in the top-right corner and select **Custom repositories**.
3. Add the URL of this GitHub repository: `https://github.com/mariusbiller/ha-junghome`.
4. Select the category as "Integration".
5. Search for "JUNG HOME" in HACS and install the integration.
6. Restart Home Assistant.

## Setup
- Find out your JUNG HOME Gateway's IP address and make sure it does not change (e.g. by making it constant in the router's DHCP settings).
- Get your access token by using the register route at `https://junghome.local/api/junghome/swagger` and confirm with JUNG HOME App or Gateway button press
- Add this integration to Home Assistant via the UI config flow.

## Support Me
If you find my work helpful, you can support me by buying me a coffee! ☕

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?username=mariusbiller&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/mariusbiller)

## Disclaimer
This project is a privately developed open-source integration for the smart home system JUNG HOME provided by Albrecht Jung GmbH & Co. KG. It is important to note that I have not been commissioned or authorized by them to create this integration.

This project is offered as-is, without any guarantee or warranty of any kind. I do not assume any responsibility for any issues, damages, or losses that may arise from the use of this integration. 
Users are encouraged to review and understand the terms and conditions of the Albrecht Jung GmbH & Co. KG's service before utilizing this integration.

Contributions and feedback from the community are welcomed and appreciated, but please keep in mind the limitations and disclaimers stated herein.

Thank you.
