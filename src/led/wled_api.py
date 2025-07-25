"""
WLED API wrapper for advanced communication
"""

import aiohttp
import asyncio
import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class WLEDInfo:
    """WLED device information"""
    version: str
    led_count: int
    name: str
    udp_port: int
    live_mode: bool
    websocket: bool
    filesystem: bool


@dataclass
class WLEDState:
    """WLED device state"""
    on: bool
    brightness: int
    transition: int
    current_preset: int
    playlist: Dict[str, Any]
    nightlight: Dict[str, Any]


class WLEDApi:
    """Advanced WLED API wrapper"""
    
    def __init__(self, ip: str, port: int = 80):
        self.ip = ip
        self.port = port
        self.base_url = f"http://{ip}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
        self.info: Optional[WLEDInfo] = None
        self.websocket = None
        
    async def connect(self, session: aiohttp.ClientSession):
        """Connect to WLED device"""
        self.session = session
        
        try:
            # Get device info
            info_data = await self._get_json("/json/info")
            if info_data:
                self.info = WLEDInfo(
                    version=info_data.get('ver', ''),
                    led_count=info_data.get('leds', {}).get('count', 30),
                    name=info_data.get('name', 'WLED'),
                    udp_port=info_data.get('udpport', 21324),
                    live_mode=info_data.get('live', False),
                    websocket=info_data.get('ws', -1) > 0,
                    filesystem=info_data.get('fs', {}).get('u', 0) > 0
                )
                logger.info(f"Connected to WLED {self.info.name} v{self.info.version}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to connect to WLED at {self.ip}: {e}")
            
        return False
        
    async def _get_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """GET request returning JSON"""
        if not self.session:
            return None
            
        try:
            url = f"{self.base_url}{endpoint}"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.warning(f"HTTP {response.status} for {endpoint}")
                    
        except Exception as e:
            logger.debug(f"GET {endpoint} failed: {e}")
            
        return None
        
    async def _post_json(self, endpoint: str, data: Dict[str, Any]) -> bool:
        """POST request with JSON data"""
        if not self.session:
            return False
            
        try:
            url = f"{self.base_url}{endpoint}"
            async with self.session.post(url, json=data) as response:
                return response.status == 200
                
        except Exception as e:
            logger.debug(f"POST {endpoint} failed: {e}")
            
        return False
        
    async def get_state(self) -> Optional[WLEDState]:
        """Get current WLED state"""
        state_data = await self._get_json("/json/state")
        if state_data:
            return WLEDState(
                on=state_data.get('on', False),
                brightness=state_data.get('bri', 0),
                transition=state_data.get('transition', 7),
                current_preset=state_data.get('ps', -1),
                playlist=state_data.get('playlist', {}),
                nightlight=state_data.get('nl', {})
            )
        return None
        
    async def set_power(self, on: bool) -> bool:
        """Turn WLED on/off"""
        return await self._post_json("/json/state", {"on": on})
        
    async def set_brightness(self, brightness: int) -> bool:
        """Set brightness (0-255)"""
        brightness = max(0, min(255, brightness))
        return await self._post_json("/json/state", {"bri": brightness})
        
    async def set_color(self, r: int, g: int, b: int, segment: int = 0) -> bool:
        """Set solid color for segment"""
        return await self._post_json("/json/state", {
            "seg": [{
                "id": segment,
                "col": [[r, g, b]]
            }]
        })
        
    async def set_effect(self, effect_id: int, segment: int = 0) -> bool:
        """Set effect for segment"""
        return await self._post_json("/json/state", {
            "seg": [{
                "id": segment,
                "fx": effect_id
            }]
        })
        
    async def set_segment(self, segment_id: int, start: int, stop: int, 
                         color: Optional[Tuple[int, int, int]] = None,
                         effect: Optional[int] = None) -> bool:
        """Configure a segment"""
        seg_data = {
            "id": segment_id,
            "start": start,
            "stop": stop
        }
        
        if color:
            seg_data["col"] = [list(color)]
            
        if effect is not None:
            seg_data["fx"] = effect
            
        return await self._post_json("/json/state", {"seg": [seg_data]})
        
    async def create_segments_for_zones(self, zones: List[Dict[str, Any]]) -> bool:
        """Create WLED segments for zones"""
        segments = []
        
        for i, zone in enumerate(zones):
            segments.append({
                "id": i,
                "start": zone["start_led"],
                "stop": zone["end_led"],
                "col": [[255, 255, 255]],  # Default white
                "fx": 0  # Solid color
            })
            
        return await self._post_json("/json/state", {"seg": segments})
        
    async def set_realtime_mode(self, enabled: bool, timeout: int = 2) -> bool:
        """Enable/disable realtime mode"""
        return await self._post_json("/json/state", {
            "live": enabled,
            "lor": timeout if enabled else 0
        })
        
    async def send_realtime_data(self, led_data: bytes) -> bool:
        """Send realtime LED data via UDP"""
        if not self.info:
            return False
            
        try:
            # Create UDP connection
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                remote_addr=(self.ip, self.info.udp_port)
            )
            
            # WLED UDP protocol
            # Format: [WARLS][timeout][start_index][data...]
            packet = bytearray()
            packet.extend(b'WARLS')  # Protocol header
            packet.append(2)  # Timeout in seconds
            packet.extend((0).to_bytes(2, 'big'))  # Start index (big endian)
            packet.extend(led_data)  # LED data
            
            transport.sendto(packet)
            transport.close()
            
            return True
            
        except Exception as e:
            logger.debug(f"UDP realtime send failed: {e}")
            return False
            
    async def get_effects_list(self) -> List[str]:
        """Get list of available effects"""
        effects_data = await self._get_json("/json/effects")
        return effects_data if effects_data else []
        
    async def get_palettes_list(self) -> List[str]:
        """Get list of available color palettes"""
        palettes_data = await self._get_json("/json/palettes")
        return palettes_data if palettes_data else []
        
    async def save_preset(self, preset_id: int, name: str) -> bool:
        """Save current state as preset"""
        return await self._post_json(f"/json/state", {
            "psave": preset_id,
            "n": name
        })
        
    async def load_preset(self, preset_id: int) -> bool:
        """Load a preset"""
        return await self._post_json("/json/state", {"ps": preset_id})
        
    async def get_presets(self) -> Dict[int, str]:
        """Get available presets"""
        presets_data = await self._get_json("/presets.json")
        if presets_data:
            return {int(k): v.get('n', f'Preset {k}') 
                   for k, v in presets_data.items() if k.isdigit()}
        return {}
        
    async def set_segment_colors_individual(self, segment_id: int, colors: List[Tuple[int, int, int]]) -> bool:
        """Set individual LED colors for a segment (advanced)"""
        # This requires the WLED device to be in realtime mode
        # and uses a more complex protocol
        
        # For now, we'll use the simpler approach of setting via HTTP
        # Individual LED control is better handled via UDP realtime
        
        if len(colors) == 0:
            return False
            
        # Calculate average color as fallback
        avg_color = [
            int(sum(c[0] for c in colors) / len(colors)),
            int(sum(c[1] for c in colors) / len(colors)),
            int(sum(c[2] for c in colors) / len(colors))
        ]
        
        return await self._post_json("/json/state", {
            "seg": [{
                "id": segment_id,
                "col": [avg_color]
            }]
        })
        
    async def ping(self) -> bool:
        """Ping WLED device to check connectivity"""
        try:
            info = await self._get_json("/json/info")
            return info is not None
        except:
            return False
            
    def get_device_info(self) -> Optional[WLEDInfo]:
        """Get cached device info"""
        return self.info
        
    def is_connected(self) -> bool:
        """Check if connected to device"""
        return self.info is not None