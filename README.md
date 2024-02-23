# homeassistant-jh

This integration shows how you would go ahead and integrate JUNG HOME into Home Assistant.


### Installation

Copy this folder to `<config_dir>/custom_components/example_light/`.

Add the following entry in your `configuration.yaml`:

```yaml
light:
  - platform: junghome
    host: HOST_HERE
    username: USERNAME_HERE
    password: PASSWORD_HERE (access token)
```
