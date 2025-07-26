# Shutdown System Improvements

## Current Implementation Issues

The current shutdown approach uses Flask-SocketIO's blocking `socketio.run()` with signal handling and force-exit fallback. While functional, it has architectural limitations.

### Current Risks:
- Flask-SocketIO may not respond to SIGINT if completely blocked
- Data corruption during mid-process operations (config saves, LED updates)
- Hardware resource cleanup may be incomplete if callbacks are running
- 3-second force-exit fallback still uses harsh `os._exit(1)`

## Recommended Future Improvements

### 1. Separate Web Server Process
Run Flask-SocketIO in a separate process that can be killed independently without affecting the main LED functionality.

```python
# Run web server in separate process that can be killed independently
import multiprocessing
import queue

def run_web_server(config_queue, status_queue, shutdown_event):
    """Web server runs in separate process"""
    # Initialize Flask-SocketIO here
    app = Flask(__name__)
    socketio = SocketIO(app)
    
    # Communicate with main process via queues
    @socketio.on('led_config_change')
    def handle_config_change(data):
        config_queue.put(('led_config', data))
    
    # Non-blocking queue check for status updates
    def check_status_updates():
        try:
            while True:
                status = status_queue.get_nowait()
                socketio.emit('status_update', status)
        except queue.Empty:
            pass
            
    # Run server with proper shutdown handling
    socketio.run(app, host="127.0.0.1", port=8080)

# In main process:
config_queue = multiprocessing.Queue()
status_queue = multiprocessing.Queue()
shutdown_event = multiprocessing.Event()

web_process = multiprocessing.Process(
    target=run_web_server, 
    args=(config_queue, status_queue, shutdown_event)
)
web_process.start()

# Main LED loop continues independently
while not shutdown_event.is_set():
    # LED processing here
    # Check config_queue for web interface changes
    # Send status updates to status_queue
    pass
```

### 2. ASGI Server Migration (FastAPI + WebSockets)
Switch to FastAPI + WebSockets for modern async approach with better shutdown handling.

```python
# Replace Flask-SocketIO with FastAPI + WebSockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="web/static"), name="static")

# Store active connections
active_connections: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Receive commands from client
            data = await websocket.receive_json()
            await handle_websocket_command(data)
    except WebSocketDisconnect:
        active_connections.remove(websocket)

async def broadcast_status(status_data):
    """Send status to all connected clients"""
    for connection in active_connections.copy():
        try:
            await connection.send_json(status_data)
        except:
            active_connections.remove(connection)

# Graceful shutdown with proper async handling
async def shutdown_handler():
    # Close all WebSocket connections
    for connection in active_connections:
        await connection.close()
    
    # Stop LED processing
    await led_controller.stop()
    await audio_processor.stop()

# uvicorn handles graceful shutdown much better than Flask
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")
```

### 3. Proper Threading with Thread-Safe Shutdown
Use thread-safe shutdown mechanism with proper coordination between components.

```python
import threading
import queue
from contextlib import contextmanager

class ThreadSafeShutdownManager:
    def __init__(self):
        self.shutdown_event = threading.Event()
        self.component_threads = []
        self.shutdown_lock = threading.RLock()
        self.active_operations = set()
        
    def register_thread(self, thread, name):
        """Register a component thread for coordinated shutdown"""
        self.component_threads.append((thread, name))
        
    @contextmanager
    def critical_operation(self, operation_name):
        """Context manager for operations that shouldn't be interrupted"""
        with self.shutdown_lock:
            if self.shutdown_event.is_set():
                raise ShutdownInProgressError()
            self.active_operations.add(operation_name)
            
        try:
            yield
        finally:
            with self.shutdown_lock:
                self.active_operations.discard(operation_name)
    
    def request_shutdown(self, timeout=10):
        """Request graceful shutdown of all components"""
        logger.info("Shutdown requested")
        self.shutdown_event.set()
        
        # Wait for active operations to complete
        deadline = time.time() + timeout
        while self.active_operations and time.time() < deadline:
            logger.info(f"Waiting for operations: {self.active_operations}")
            time.sleep(0.1)
            
        # Stop all registered threads
        for thread, name in self.component_threads:
            logger.info(f"Stopping {name}...")
            thread.join(timeout=2)
            if thread.is_alive():
                logger.warning(f"{name} did not stop gracefully")

# Usage in components:
shutdown_manager = ThreadSafeShutdownManager()

class LEDController:
    def update_config(self, config):
        with shutdown_manager.critical_operation("led_config_update"):
            # This operation won't be interrupted by shutdown
            self.save_led_config(config)
            
    def run(self):
        while not shutdown_manager.shutdown_event.is_set():
            # Main LED loop
            self.update_leds()
            time.sleep(1/60)  # 60 FPS

# Web server in separate thread
def run_web_server():
    # Flask-SocketIO with shutdown coordination
    @app.route('/api/system/shutdown', methods=['POST'])
    def shutdown():
        shutdown_manager.request_shutdown()
        return jsonify({'success': True})
        
    socketio.run(app, host="127.0.0.1", port=8080)

web_thread = threading.Thread(target=run_web_server, daemon=False)
shutdown_manager.register_thread(web_thread, "web_server")
web_thread.start()
```

### 4. Graceful Degradation Architecture
Allow the main LED functionality to continue even if web interface fails.

```python
class CircLightsCore:
    """Core LED functionality that runs independently of web interface"""
    
    def __init__(self):
        self.audio_processor = AudioProcessor()
        self.led_controller = LEDController()
        self.running = True
        self.web_interface = None
        
    async def start_core(self):
        """Start core LED functionality"""
        logger.info("Starting CircLights core...")
        await self.audio_processor.start()
        await self.led_controller.start()
        
        # Core processing loop - runs regardless of web interface
        asyncio.create_task(self.core_processing_loop())
        
    async def core_processing_loop(self):
        """Main LED processing - independent of web interface"""
        while self.running:
            try:
                # Get audio features
                features = self.audio_processor.get_current_features()
                
                # Update LEDs based on audio
                self.led_controller.update_from_audio(features)
                
                await asyncio.sleep(1/60)  # 60 FPS
                
            except Exception as e:
                logger.error(f"Core processing error: {e}")
                # Continue running even if there are errors
                await asyncio.sleep(0.1)
                
    async def start_web_interface(self):
        """Start web interface - optional component"""
        try:
            logger.info("Starting web interface...")
            self.web_interface = WebInterface(self)
            await self.web_interface.start()
            logger.info("Web interface started successfully")
            
        except Exception as e:
            logger.warning(f"Web interface failed to start: {e}")
            logger.info("Continuing with core LED functionality only")
            self.web_interface = None
            
    def get_status(self):
        """Get system status - used by web interface if available"""
        return {
            'core_running': self.running,
            'audio_active': self.audio_processor.is_active(),
            'led_active': self.led_controller.is_active(),
            'web_interface': self.web_interface is not None
        }
        
    async def shutdown(self):
        """Graceful shutdown of all components"""
        logger.info("Shutting down CircLights...")
        self.running = False
        
        # Stop web interface first (non-essential)
        if self.web_interface:
            try:
                await self.web_interface.stop()
            except Exception as e:
                logger.warning(f"Web interface shutdown error: {e}")
                
        # Stop core components
        await self.led_controller.stop()
        await self.audio_processor.stop()
        logger.info("CircLights shutdown complete")

# Main startup with degradation handling
async def main():
    core = CircLightsCore()
    
    # Always start core functionality
    await core.start_core()
    
    # Try to start web interface, but continue without it if it fails
    await core.start_web_interface()
    
    # Setup signal handling
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        asyncio.create_task(core.shutdown())
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep running until shutdown
    try:
        while core.running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await core.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

### 3. Proper Shutdown Coordination
```python
class ComponentManager:
    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.components = []
        
    async def graceful_shutdown(self):
        # Stop components in dependency order
        for component in reversed(self.components):
            await component.stop()
            
    async def emergency_shutdown(self, timeout=5):
        try:
            await asyncio.wait_for(self.graceful_shutdown(), timeout)
        except asyncio.TimeoutError:
            logger.warning("Graceful shutdown timed out, forcing exit")
            # Still need force exit but with better coordination
```

### 4. State Locking During Critical Operations
```python
import asyncio
from contextlib import asynccontextmanager

class SafeConfigManager:
    def __init__(self):
        self._operation_lock = asyncio.Lock()
        self._shutdown_requested = False
        
    @asynccontextmanager
    async def critical_operation(self, operation_name):
        if self._shutdown_requested:
            raise ShutdownInProgressError()
            
        async with self._operation_lock:
            logger.debug(f"Starting critical operation: {operation_name}")
            try:
                yield
            finally:
                logger.debug(f"Completed critical operation: {operation_name}")
```

### 5. Hardware Resource Management
```python
class HardwareManager:
    def __init__(self):
        self.devices = []
        self.cleanup_handlers = []
        
    def register_cleanup(self, handler):
        self.cleanup_handlers.append(handler)
        
    async def safe_shutdown(self):
        for handler in reversed(self.cleanup_handlers):
            try:
                await handler()
            except Exception as e:
                logger.error(f"Cleanup handler failed: {e}")
                # Continue with other cleanup
```

## Implementation Priority

1. **High Priority**: State locking during config saves and LED updates
2. **Medium Priority**: Separate web server process 
3. **Low Priority**: Migrate to FastAPI (breaking change)

## WLED Integration Improvements (Based on LedFx Analysis)

### Future High-Impact Improvements:

#### 1. **Auto-Discovery of WLED Devices**
```python
# Implement network scanning for WLED devices
class WLEDDiscovery:
    async def scan_network(self):
        # mDNS/Bonjour discovery for WLED devices
        # Network broadcast discovery
        # Return list of discovered devices with capabilities
        pass
```

#### 2. **Adaptive Protocol Selection**
```python
# Choose best protocol based on device capabilities and LED count
protocols = {
    'WARLS': 'Basic UDP, good for <500 LEDs',
    'DDP': 'Better for large strips >500 LEDs', 
    'E131': 'DMX-compatible, professional use',
    'HTTP': 'Fallback only, slow but reliable'
}
```

#### 3. **Traffic Optimization**
```python
# Only send data when frame changes (like LedFx does)
class TrafficOptimizer:
    def should_send_frame(self, new_data, last_data):
        return not np.array_equal(new_data, last_data)
```

#### 4. **Advanced Device Configuration**
- Auto-detect LED count from device
- Support RGBW strips automatically  
- Handle multiple segments/zones per device
- Device capability caching

### Current Workarounds

Until these improvements are implemented:
- Save configuration more frequently to minimize data loss risk
- Add retry logic for hardware operations
- Monitor for shutdown requests in long-running operations
- Use the web interface shutdown button instead of Ctrl+C when possible

## Notes

- The current approach is acceptable for development/home use
- Production deployment would require at least the state locking improvements
- Consider using systemd or similar service manager for better process control
- Test shutdown behavior thoroughly after any changes to core components