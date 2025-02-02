import aiohttp
import logging

# Set up logging for this module
_LOGGER = logging.getLogger(__name__)

class JunghomeGateway:
    @staticmethod
    async def request_devices(host: str, token: str):
        """
        Requests a list of devices from the api-junghome using the specified host and token.

        Parameters:
        host (str): hostename or IP address of the API host, excluding 'https://'.
        token (str): The authentication token for API access.

        Returns:
        list or None: A list of device dictionaries if the request is successful, None otherwise.
        """
        # Create URL
        url = f"https://{host}/api/junghome/functions/"
        _LOGGER.info(f"Requesting devices from {url}...")

        # Use the generic HTTP GET request function
        devices = await JunghomeGateway.http_get_request(url, token)

        if devices is None:
            _LOGGER.error("Failed to retrieve Jung Home devices.")
            return None

        _LOGGER.debug(f"Devices response: {devices}")
        return devices

    # ==================================================================================
    # HTTP HELPER FUNCTIONS
    # ==================================================================================

    @staticmethod
    async def http_get_request(url: str, token: str):
        """
        Sends an HTTP GET request to the specified URL with authorization provided by the token.

        Parameters:
            url (str):      The URL to which the GET request is sent.
            token (str):    The authorization token included in the request headers.

        Returns:
            dict:   The JSON response from the server if the request is successful.
            None:   Returns None if the request fails or raises an exception.
        """
        # Create headers
        headers = {
            "accept": "application/json",
            "token": token
        }
        
        _LOGGER.debug(f"Sending GET request to {url} with headers {headers}...")

        # Send request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, ssl=False) as response:
                    response.raise_for_status()
                    _LOGGER.info(f"GET request to {url} succeeded.")
                    return await response.json()
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to get data from {url}: {e}")
            return None

    @staticmethod
    async def http_patch_request(url: str, token: str, data: dict):
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
        # Create headers
        headers = {
            "accept": "application/json",
            "Content-Type": "application/json",
            "token": token
        }
        
        _LOGGER.debug(f"Sending PATCH request to {url} with headers {headers} and data {data}...")

        # Send request
        try:
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=data, ssl=False) as response:
                    response.raise_for_status()
                    _LOGGER.info(f"PATCH request to {url} succeeded.")
                    return await response.json()
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to update data on {url}: {e}")
            return None