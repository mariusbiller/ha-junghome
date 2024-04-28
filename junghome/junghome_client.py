
import requests



def request_devices(host: str, token: str):
    """
    Requests a list of devices from the api-junghome using the specified host and token.

    Parameters:
    host (str): hostename or ip address of the API host, excluding 'https://'.
    token (str): The authentication token for API access.

    Returns:
    list or None: A list of device dictionaries if the request is successful, None otherwise.
    """
    
    # Disabling SSL verification
    requests.packages.urllib3.disable_warnings()
    
    # create header
    url = 'https://' + host + '/api/junghome/functions/'
    headers = {
        'accept': 'application/json',
        'token': token
    }
    
    # request junghome devices
    response = requests.get(url, headers=headers, verify=False)
    if response.status_code != 200:
        print(f"request junghome devices failed with status code: {response.status_code}")
        if response.status_code == 401: print("invalid password or token")
        return None
    
    # return devices
    devices = response.json()
    return devices

