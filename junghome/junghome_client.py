
import requests

class JunghomeGateway:

    def request_devices(host: str, token: str):
        """
        Requests a list of devices from the api-junghome using the specified host and token.

        Parameters:
        host (str): hostename or ip address of the API host, excluding 'https://'.
        token (str): The authentication token for API access.

        Returns:
        list or None: A list of device dictionaries if the request is successful, None otherwise.
        """
        
        # create url
        url = 'https://' + host + '/api/junghome/functions/'
        
        # Use the generic HTTP GET request function
        devices = JunghomeGateway.http_get_request(url, token)
        
        if devices is None:
            print("failed to get jung home devices.")
            return None
        
        return devices



    # ==================================================================================
    # HTTP HELPER FUNCTIONS
    # ==================================================================================

    def http_get_request(url, token):
        """
        Sends an HTTP GET request to the specified URL with authorization provided by the token.

        Parameters:
            url (str):      The URL to which the GET request is sent.
            token (str):    The authorization token included in the request headers.

        Returns:
            dict:   The JSON response from the server if the request is successful.
            None:   Returns None if the request fails or raises an exception.
        """
        
        # Disabling SSL verification
        requests.packages.urllib3.disable_warnings()
        
        # create header
        headers = {
            'accept': 'application/json',
            'token': token
        }
        
        # send request
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"failed to get data: {e}")
            return None




    def http_patch_request(url, token, data):
        """
        Sends an HTTP PATCH request to the specified URL with the provided data and authorization token.

        Parameters:
            url (str):      The URL to which the PATCH request is sent.
            data (dict):    The data to be sent in the request body, typically in JSON format.
            token (str):    The authorization token included in the request headers.

        Returns:
            dict:   The JSON response from the server if the request is successful.
            None:   Returns None if the request encounters an error or raises an exception.
        """
        
        # Disabling SSL verification
        requests.packages.urllib3.disable_warnings()
        
        # create header
        headers = {
            'accept': 'application/json',
            'Content-Type': 'application/json',
            'token': token
        }
        
        # send request
        try:
            response = requests.patch(url, headers=headers, json=data, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"failed to update data: {e}")
            return None
