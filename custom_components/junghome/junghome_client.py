import aiohttp
import asyncio
import json
import logging
from typing import Callable, Optional

# Set up logging for this module
_LOGGER = logging.getLogger(__name__)

class JunghomeGateway:
    def __init__(self, host: str, token: str):
        """Initialize the JunghomeGateway with host and token."""
        self.host = host
        self.token = token
        self._ws_session = None
        self._ws_connection = None
        self._ws_task = None
        self._reconnect_task = None
        self._data_callback = None
        self._is_connected = False
        self._should_reconnect = True
        self._functions = {}
        self._groups = {}
        self._scenes = {}

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
            _LOGGER.error("Failed to retrieve JUNG HOME devices.")
            return None

        _LOGGER.debug(f"Devices response: {devices}")
        return devices

    @staticmethod
    async def request_hub_config(host: str, token: str):
        """
        Requests hub configuration from the api-junghome using the specified host and token.

        Parameters:
        host (str): hostename or IP address of the API host, excluding 'https://'.
        token (str): The authentication token for API access.

        Returns:
        dict or None: A dictionary with hub configuration if the request is successful, None otherwise.
        """
        # Create URL
        url = f"https://{host}/api/junghome/config/"
        _LOGGER.info(f"Requesting hub config from {url}...")

        # Use the generic HTTP GET request function
        config = await JunghomeGateway.http_get_request(url, token)

        if config is None:
            _LOGGER.error("Failed to retrieve JUNG HOME gateway configuration.")
            return None

        _LOGGER.debug(f"Hub config response: {config}")
        return config

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
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                _LOGGER.error(f"Authentication failed for {url}: {e}")
            else:
                _LOGGER.error(f"HTTP error {e.status} for {url}: {e}")
            return None
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
                    
                    # Get response text first, then parse as JSON
                    response_text = await response.text()
                    if response_text:
                        try:
                            import json
                            return json.loads(response_text)
                        except json.JSONDecodeError as json_err:
                            _LOGGER.warning(f"Failed to parse JSON response from {url}: {json_err}. Response: {response_text}")
                    
                    # If no response body or JSON parsing failed, but request was successful
                    return {"success": True}
                    
        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                _LOGGER.error(f"Authentication failed for {url}: {e}")
            elif e.status == 404:
                _LOGGER.error(f"Device/datapoint not found for {url}: {e}")
            else:
                _LOGGER.error(f"HTTP error {e.status} for {url}: {e}")
            return None
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Failed to update data on {url}: {e}")
            return None

    # ==================================================================================
    # WEBSOCKET FUNCTIONS
    # ==================================================================================

    async def connect_websocket(self, data_callback: Callable):
        """Connect to the WebSocket endpoint and start listening for updates."""
        self._data_callback = data_callback
        self._should_reconnect = True
        
        if self._ws_task is None or self._ws_task.done():
            self._ws_task = asyncio.create_task(self._websocket_handler())

    async def disconnect_websocket(self):
        """Disconnect from the WebSocket."""
        self._should_reconnect = False
        
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            
        if self._ws_connection and not self._ws_connection.closed:
            await self._ws_connection.close()
            
        if self._ws_session:
            await self._ws_session.close()
            
        if self._ws_task and not self._ws_task.done():
            self._ws_task.cancel()
            
        self._is_connected = False

    async def _websocket_handler(self):
        """Handle WebSocket connection and reconnection logic."""
        while self._should_reconnect:
            try:
                await self._connect_and_listen()
            except Exception as err:
                _LOGGER.error("WebSocket connection failed: %s", err)
                self._is_connected = False
                
                if self._should_reconnect:
                    _LOGGER.info("Retrying WebSocket connection in 5 seconds...")
                    await asyncio.sleep(5)

    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages."""
        import time

        # Call request_devices once before connection to unlock caching
        try:
            await self.request_devices(self.host, self.token)
            _LOGGER.info("Initial request_devices call completed to unlock caching")
        except Exception as e:
            _LOGGER.warning("Failed to call request_devices after websocket connection: %s", e)
        
        # Add timestamp to bust server-side cache
        timestamp = int(time.time() * 1000)
        ws_url = f"wss://{self.host}/ws?t={timestamp}"
        headers = {"token": self.token}
        
        _LOGGER.info("Connecting to WebSocket at %s", ws_url)
        
        self._ws_session = aiohttp.ClientSession()
        self._ws_connection = await self._ws_session.ws_connect(
            ws_url, 
            headers=headers, 
            ssl=False,
            heartbeat=30
        )
        
        self._is_connected = True
        _LOGGER.info("WebSocket connected successfully")
        
        
        async for msg in self._ws_connection:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_websocket_message(data)
                except json.JSONDecodeError as err:
                    _LOGGER.warning("Failed to decode WebSocket message: %s, raw data: %s", err, msg.data)
                    
            elif msg.type == aiohttp.WSMsgType.ERROR:
                _LOGGER.error("WebSocket error: %s", self._ws_connection.exception())
                break
                
            elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED):
                _LOGGER.info("WebSocket connection closed")
                break
                
        self._is_connected = False
        
        if self._ws_session:
            await self._ws_session.close()

    async def _handle_websocket_message(self, data: dict):
        """Handle incoming WebSocket messages."""
        msg_type = data.get("type")
        msg_data = data.get("data")
        
        _LOGGER.debug("Received WebSocket message: %s", data)
        
        if msg_type == "message":
            _LOGGER.info("Gateway message: %s", msg_data)
            
        elif msg_type == "version":
            _LOGGER.info("Gateway version: %s", msg_data)
            
        elif msg_type == "functions":
            self._functions = {func["id"]: func for func in msg_data}
            _LOGGER.info("Received %d functions", len(self._functions))
            if self._data_callback:
                await self._data_callback("functions", self._functions)
                
        elif msg_type == "groups":
            self._groups = {group["id"]: group for group in msg_data}
            _LOGGER.info("Received %d groups", len(self._groups))
            if self._data_callback:
                await self._data_callback("groups", self._groups)
                
        elif msg_type == "scenes":
            self._scenes = {scene["id"]: scene for scene in msg_data}
            _LOGGER.info("Received %d scenes", len(self._scenes))
            if self._data_callback:
                await self._data_callback("scenes", self._scenes)
                
        elif msg_type == "datapoint":
            if self._data_callback:
                await self._data_callback("datapoint", msg_data)

    @property
    def is_connected(self) -> bool:
        """Return True if WebSocket is connected."""
        return self._is_connected

    @property
    def functions(self) -> dict:
        """Return functions data."""
        return self._functions

    @property
    def groups(self) -> dict:
        """Return groups data."""
        return self._groups

    @property
    def scenes(self) -> dict:
        """Return scenes data."""
        return self._scenes