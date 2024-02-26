# homeassistant-jh

This integration shows how you would go ahead and integrate JUNG HOME devices into Home Assistant.


## Installation

Copy this folder to `<config_dir>/custom_components/junghome/`.

Add the following entry in your `configuration.yaml`:

```yaml
light:
  - platform: junghome
    host: junghome.local
    username: Home Assistant User
    password:  <access token>
```

## Support Me

If you find my work helpful, you can support me by buying me a coffee! ☕

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?username=mariusbiller&button_colour=FFDD00&font_colour=000000&font_family=Cookie&outline_colour=000000&coffee_colour=ffffff)](https://www.buymeacoffee.com/mariusbiller)


## Disclaimer

This project is a privately developed open-source integration for the smart home system JUNG HOME provided by Albrecht Jung GmbH & Co. KG. It is important to note that I have not been commissioned or authorized by them to create this integration.

This project is offered as-is, without any guarantee or warranty of any kind. I do not assume any responsibility for any issues, damages, or losses that may arise from the use of this integration. 
Users are encouraged to review and understand the terms and conditions of the Albrecht Jung GmbH & Co. KG's service before utilizing this integration.

Contributions and feedback from the community are welcomed and appreciated, but please keep in mind the limitations and disclaimers stated herein.

Thank you.
