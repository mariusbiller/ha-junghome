# ha-junghome
This is a bare minimum example integration showing how to integrate JUNG HOME devices into Home Assistant.

## Supported device types
- OnOff Light
- Dimmable Light
- Tuneable White Light (switching and brightness only)
- Socket (displayed as Light)
- Window Cover

>**hint:**
*Please note that the provided integration is a bare minimum example and may have limitations regarding its quality and functionality.*

## Installation
- Copy this folder to `<config_dir>/custom_components/junghome/`
- Find out your JUNG HOME Gateway's ip address and make sure ist does not change 
  e.g. by make it constant in the router's DHCP settings
- get your access token by register at `https://junghome.local/api/junghome/swagger` 
- Add this integragration to Home Assistant via the UI config flow 

## Support Me
If you find my work helpful, you can support me by buying me a coffee! ☕

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?username=mariusbiller&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/mariusbiller)


## Disclaimer

This project is a privately developed open-source integration for the smart home system JUNG HOME provided by Albrecht Jung GmbH & Co. KG. It is important to note that I have not been commissioned or authorized by them to create this integration.

This project is offered as-is, without any guarantee or warranty of any kind. I do not assume any responsibility for any issues, damages, or losses that may arise from the use of this integration. 
Users are encouraged to review and understand the terms and conditions of the Albrecht Jung GmbH & Co. KG's service before utilizing this integration.

Contributions and feedback from the community are welcomed and appreciated, but please keep in mind the limitations and disclaimers stated herein.

Thank you.
