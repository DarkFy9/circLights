"""
WLED LED strip controller
Handles communication with WLED devices over WiFi
"""

import asyncio
import aiohttp
import logging
import numpy as np
import time
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from zeroconf import ServiceBrowser, Zeroconf
import json

logger = logging.getLogger(__name__)


@dataclass
class LEDZone:
    """Represents a zone on the LED strip"""
    name: str
    start_percent: float  # 0.0-1.0
    end_percent: float    # 0.0-1.0
    start_led: int       # Calculated from percentages
    end_led: int         # Calculated from percentages
    enabled: bool = True


@dataclass
class WLEDDevice:
    """WLED device information"""
    name: str
    ip: str
    port: int = 80
    led_count: int = 30
    online: bool = False
    version: str = ""
    mac: str = ""


class LEDController:
    """Controls WLED devices over WiFi"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        
        # Device configuration
        self.devices: List[WLEDDevice] = []
        self.primary_device: Optional[WLEDDevice] = None
        
        # LED configuration
        self.led_count = 30
        self.update_rate = 60  # Target FPS
        self.brightness = 255
        
        # Network
        self.session: Optional[aiohttp.ClientSession] = None
        self.discovery_service = None
        self.udp_socket = None
        
        # LED data
        self.led_data = np.zeros((self.led_count, 3), dtype=np.uint8)  # RGB
        self.zones: List[LEDZone] = []
        
        # Performance tracking
        self.last_update_time = 0.0
        self.update_interval = 1.0 / self.update_rate
        self.frame_times = []
        
        # State management
        self.running = False
        self.update_lock = asyncio.Lock()
        
        logger.info("LEDController initialized")
        
    async def start(self):
        """Start the LED controller"""
        if self.running:
            logger.warning("LEDController already running")
            return
            
        self.running = True
        logger.info("Starting LEDController...")
        
        try:
            # Create HTTP session for device discovery/config
            timeout = aiohttp.ClientTimeout(total=5.0)  # Longer timeout for discovery
            self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Create UDP socket for LED data transmission
            import socket
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Start device discovery
            await self._start_discovery()
            
            # Initialize default device if configured
            await self._initialize_devices()
            
            logger.info("LEDController started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start LEDController: {e}")
            self.running = False
            raise
            
    async def stop(self):
        """Stop the LED controller"""
        if not self.running:
            return
            
        logger.info("Stopping LEDController...")
        self.running = False
        
        # Close HTTP session
        if self.session:
            await self.session.close()
            
        # Close UDP socket
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            
        # Stop discovery
        if self.discovery_service:
            self.discovery_service.cancel()
            self.session = None
            
        logger.info("LEDController stopped")
        
    async def _start_discovery(self):
        """Start WLED device discovery"""
        try:
            zeroconf = Zeroconf()
            browser = ServiceBrowser(zeroconf, "_http._tcp.local.", self._on_service_found)
            logger.info("Started WLED device discovery")
        except Exception as e:
            logger.warning(f"Could not start device discovery: {e}")
            
    def _on_service_found(self, zeroconf, service_type, name):
        """Handle discovered network service"""
        try:
            info = zeroconf.get_service_info(service_type, name)
            if info and "wled" in name.lower():
                device_ip = str(info.addresses[0])
                device_name = info.server.rstrip('.')
                
                # Add discovered device
                device = WLEDDevice(
                    name=device_name,
                    ip=device_ip,
                    port=info.port or 80
                )
                
                if device not in self.devices:
                    self.devices.append(device)
                    logger.info(f"Discovered WLED device: {device.name} at {device.ip}")
                    
        except Exception as e:
            logger.debug(f"Error processing discovered service: {e}")
            
    async def _initialize_devices(self):
        """Initialize configured devices"""
        # For now, create a default device if none configured
        if not self.devices:
            default_ip = getattr(self.config_manager, 'wled_ip', '192.168.1.100')
            default_device = WLEDDevice(
                name="Default WLED",
                ip=default_ip,
                led_count=self.led_count
            )
            self.devices.append(default_device)
            
        # Set primary device
        if self.devices and not self.primary_device:
            self.primary_device = self.devices[0]
            await self._probe_device(self.primary_device)
            
    async def _probe_device(self, device: WLEDDevice) -> bool:
        """Probe WLED device for information"""
        try:
            url = f"http://{device.ip}:{device.port}/json/info"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    device.version = data.get('ver', '')
                    device.mac = data.get('mac', '')
                    device.online = True
                    
                    # Get LED count from state
                    state_url = f"http://{device.ip}:{device.port}/json/state"
                    async with self.session.get(state_url) as state_response:
                        if state_response.status == 200:
                            state_data = await state_response.json()
                            # WLED doesn't directly report LED count in state, use configured value
                            pass
                            
                    logger.info(f"Device {device.name} online - Version: {device.version}")
                    return True
                    
        except Exception as e:
            logger.debug(f"Failed to probe device {device.name}: {e}")
            device.online = False
            
        return False
        
    def add_device(self, name: str, ip: str, port: int = 80, led_count: int = 30):
        """Add a WLED device"""
        device = WLEDDevice(
            name=name,
            ip=ip,
            port=port,
            led_count=led_count
        )
        
        self.devices.append(device)
        
        if not self.primary_device:
            self.primary_device = device
            
        logger.info(f"Added WLED device: {name} at {ip}")
        
    async def _test_device_connectivity(self, device_ip: str):
        """Test connectivity to a WLED device and mark it online"""
        for device in self.devices:
            if device.ip == device_ip:
                try:
                    if self.session:
                        url = f"http://{device.ip}:{device.port}/json/info"
                        async with self.session.get(url) as response:
                            if response.status == 200:
                                device.online = True
                                logger.info(f"Device {device.name} is online")
                                return True
                except Exception as e:
                    logger.warning(f"Device {device.name} connectivity test failed: {e}")
                
                device.online = False
                return False
        return False
        
    def set_primary_device(self, device_ip: str):
        """Set primary WLED device by IP"""
        for device in self.devices:
            if device.ip == device_ip:
                self.primary_device = device
                self.led_count = device.led_count
                self._update_led_data_size()
                logger.info(f"Set primary device to {device.name}")
                return True
        return False
        
    def _update_led_data_size(self):
        """Update LED data array size"""
        if self.led_count != self.led_data.shape[0]:
            self.led_data = np.zeros((self.led_count, 3), dtype=np.uint8)
            self._update_zone_led_indices()
            
    def set_led_count(self, count: int):
        """Set number of LEDs"""
        self.led_count = max(1, min(1000, count))
        self._update_led_data_size()
        logger.info(f"LED count set to {self.led_count}")
        
    def add_zone(self, name: str, start_percent: float, end_percent: float) -> LEDZone:
        """Add a LED zone"""
        # Validate percentages
        start_percent = max(0.0, min(1.0, start_percent))
        end_percent = max(start_percent, min(1.0, end_percent))
        
        # Calculate LED indices
        start_led = int(start_percent * self.led_count)
        end_led = int(end_percent * self.led_count)
        
        zone = LEDZone(
            name=name,
            start_percent=start_percent,
            end_percent=end_percent,
            start_led=start_led,
            end_led=end_led
        )
        
        self.zones.append(zone)
        logger.info(f"Added zone '{name}': LEDs {start_led}-{end_led}")
        return zone
        
    def remove_zone(self, name: str) -> bool:
        """Remove a zone by name"""
        for i, zone in enumerate(self.zones):
            if zone.name == name:
                del self.zones[i]
                logger.info(f"Removed zone '{name}'")
                return True
        return False
        
    def _update_zone_led_indices(self):
        """Update LED indices for all zones when LED count changes"""
        for zone in self.zones:
            zone.start_led = int(zone.start_percent * self.led_count)
            zone.end_led = int(zone.end_percent * self.led_count)
            
    def get_zone_leds(self, zone: LEDZone) -> Tuple[int, int]:
        """Get LED range for a zone"""
        return zone.start_led, zone.end_led
        
    def set_zone_color(self, zone: LEDZone, color: Tuple[int, int, int]):
        """Set solid color for a zone"""
        start_led, end_led = self.get_zone_leds(zone)
        if zone.enabled:
            self.led_data[start_led:end_led] = color
            
    def set_zone_colors(self, zone: LEDZone, colors: np.ndarray):
        """Set individual colors for LEDs in a zone"""
        start_led, end_led = self.get_zone_leds(zone)
        zone_size = end_led - start_led
        
        if zone.enabled and len(colors) > 0:
            # Resize colors to fit zone
            if len(colors) != zone_size:
                colors = np.resize(colors, (zone_size, 3))
            self.led_data[start_led:end_led] = colors
            
    def set_all_leds(self, colors: np.ndarray):
        """Set all LED colors"""
        if len(colors) == self.led_count:
            self.led_data = colors.astype(np.uint8)
        else:
            # Resize to fit
            resized = np.resize(colors, (self.led_count, 3))
            self.led_data = resized.astype(np.uint8)
            
    def clear_leds(self):
        """Turn off all LEDs"""
        self.led_data.fill(0)
        
    def set_brightness(self, brightness: int):
        """Set global brightness (0-255)"""
        self.brightness = max(0, min(255, brightness))
        
    async def update_leds(self, force: bool = False):
        """Send LED data to WLED device"""
        if not self.primary_device or not self.primary_device.online:
            return False
            
        current_time = time.time()
        
        # Rate limiting
        if not force and (current_time - self.last_update_time) < self.update_interval:
            return True
            
        async with self.update_lock:
            try:
                # Apply brightness
                adjusted_data = (self.led_data * (self.brightness / 255)).astype(np.uint8)
                
                # Send LED data via UDP (much faster than HTTP)
                success = await self._send_udp_data(adjusted_data)
                
                if success:
                    self.last_update_time = current_time
                    
                    # Track performance
                    self.frame_times.append(current_time)
                    if len(self.frame_times) > 100:
                        self.frame_times.pop(0)
                        
                    return True
                else:
                    logger.warning(f"WLED UDP update failed")
                        
            except Exception as e:
                logger.error(f"Error updating LEDs: {e}")
                self.primary_device.online = False
                
        return False
        
    async def _send_udp_data(self, led_data: np.ndarray):
        """Send LED data via UDP for high performance"""
        if not self.primary_device or not self.udp_socket:
            return False
            
        try:
            # WLED UDP protocol: [WARLS][timeout][start_index][data...]
            udp_data = bytearray()
            udp_data.extend(b'WARLS')  # Protocol identifier
            udp_data.append(2)  # Timeout in seconds
            udp_data.extend((0).to_bytes(2, 'big'))  # Start index (16-bit big endian)
            
            # Add LED data (RGB format)
            for r, g, b in led_data:
                udp_data.extend([r, g, b])
            
            # Send UDP packet
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.udp_socket.sendto(
                    udp_data, 
                    (self.primary_device.ip, 21324)  # WLED UDP port
                )
            )
            
            logger.debug(f"Sent {len(udp_data)} bytes via UDP to {self.primary_device.ip}")
            return True
            
        except Exception as e:
            logger.error(f"UDP send error: {e}")
            return False
            
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics"""
        if len(self.frame_times) < 2:
            return {"fps": 0.0, "avg_frame_time": 0.0}
            
        recent_times = self.frame_times[-20:]  # Last 20 frames
        intervals = [recent_times[i] - recent_times[i-1] for i in range(1, len(recent_times))]
        
        if intervals:
            avg_interval = np.mean(intervals)
            fps = 1.0 / avg_interval if avg_interval > 0 else 0.0
            return {
                "fps": fps,
                "avg_frame_time": avg_interval * 1000,  # ms
                "target_fps": self.update_rate
            }
            
        return {"fps": 0.0, "avg_frame_time": 0.0, "target_fps": self.update_rate}
        
    def get_device_status(self) -> List[Dict[str, Any]]:
        """Get status of all devices"""
        return [
            {
                "name": device.name,
                "ip": device.ip,
                "online": device.online,
                "version": device.version,
                "is_primary": device == self.primary_device
            }
            for device in self.devices
        ]