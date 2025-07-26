// CircLights Web Interface JavaScript

class CircLightsApp {
    constructor() {
        this.socket = null;
        this.audioCanvas = null;
        this.audioCtx = null;
        this.ledCanvas = null;
        this.ledCtx = null;
        this.isConnected = false;
        this.currentStatus = null;
        
        this.init();
    }
    
    init() {
        this.initSocket();
        this.initCanvas();
        this.initEventListeners();
        this.loadInitialData();
    }
    
    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            this.isConnected = true;
            this.updateConnectionStatus('Connected', true);
            this.socket.emit('request_status');
        });
        
        this.socket.on('disconnect', () => {
            this.isConnected = false;
            this.updateConnectionStatus('Disconnected', false);
        });
        
        this.socket.on('status_update', (data) => {
            this.currentStatus = data;
            this.updateUI(data);
        });
        
        this.socket.on('realtime_update', (data) => {
            this.updateRealtimeData(data);
        });
    }
    
    initCanvas() {
        // Audio visualizer canvas
        this.audioCanvas = document.getElementById('audio-canvas');
        if (this.audioCanvas) {
            this.audioCtx = this.audioCanvas.getContext('2d');
            this.audioCanvas.width = this.audioCanvas.offsetWidth;
            this.audioCanvas.height = this.audioCanvas.offsetHeight;
        }
        
        // LED strip visualizer canvas
        this.ledCanvas = document.getElementById('led-strip-canvas');
        if (this.ledCanvas) {
            this.ledCtx = this.ledCanvas.getContext('2d');
            this.ledCanvas.width = this.ledCanvas.offsetWidth;
            this.ledCanvas.height = this.ledCanvas.offsetHeight;
        }
    }
    
    initEventListeners() {
        // Audio source selection
        const audioSource = document.getElementById('audio-source');
        if (audioSource) {
            audioSource.addEventListener('change', this.handleAudioSourceChange.bind(this));
        }
        
        // Audio device selection
        const audioDevice = document.getElementById('audio-device');
        if (audioDevice) {
            audioDevice.addEventListener('change', this.handleAudioDeviceChange.bind(this));
        }
        
        // MP3 controls
        const mp3File = document.getElementById('mp3-file');
        if (mp3File) {
            mp3File.addEventListener('change', this.handleMP3FileChange.bind(this));
        }
        
        document.getElementById('mp3-play')?.addEventListener('click', () => this.controlMP3('play'));
        document.getElementById('mp3-pause')?.addEventListener('click', () => this.controlMP3('pause'));
        document.getElementById('mp3-stop')?.addEventListener('click', () => this.controlMP3('stop'));
        
        const mp3Seek = document.getElementById('mp3-seek');
        if (mp3Seek) {
            mp3Seek.addEventListener('input', this.handleMP3Seek.bind(this));
        }
        
        // LED controls
        const ledCount = document.getElementById('led-count');
        if (ledCount) {
            ledCount.addEventListener('change', this.handleLEDConfigChange.bind(this));
        }
        
        const brightness = document.getElementById('brightness');
        if (brightness) {
            brightness.addEventListener('input', this.handleBrightnessChange.bind(this));
        }
        
        const wledIP = document.getElementById('wled-ip');
        if (wledIP) {
            wledIP.addEventListener('change', this.handleLEDConfigChange.bind(this));
        }
        
        // LED test buttons
        document.getElementById('test-rainbow')?.addEventListener('click', () => this.testLEDs('rainbow'));
        document.getElementById('test-white')?.addEventListener('click', () => this.testLEDs('white'));
        document.getElementById('test-off')?.addEventListener('click', () => this.testLEDs('off'));
        
        // WLED connection test
        document.getElementById('test-wled-connection')?.addEventListener('click', this.testWLEDConnection.bind(this));
        
        // Zone management
        document.getElementById('add-zone')?.addEventListener('click', this.showAddZoneModal.bind(this));
        document.getElementById('clear-zones')?.addEventListener('click', this.clearAllZones.bind(this));
        document.getElementById('save-zone')?.addEventListener('click', this.saveZone.bind(this));
        document.getElementById('cancel-zone')?.addEventListener('click', this.hideAddZoneModal.bind(this));
        
        // Zone sensitivity slider
        const zoneSensitivity = document.getElementById('zone-sensitivity');
        if (zoneSensitivity) {
            zoneSensitivity.addEventListener('input', (e) => {
                document.getElementById('zone-sensitivity-value').textContent = e.target.value;
            });
        }
        
        // Preset controls
        document.getElementById('load-preset')?.addEventListener('click', this.loadPreset.bind(this));
        document.getElementById('save-preset')?.addEventListener('click', this.savePreset.bind(this));
        
        // System controls
        document.getElementById('safe-shutdown')?.addEventListener('click', this.safeShutdown.bind(this));
        
        // Window resize
        window.addEventListener('resize', this.handleResize.bind(this));
    }
    
    updateConnectionStatus(status, connected) {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = status;
            statusElement.className = connected ? 'status-connected' : 'status-disconnected';
        }
    }
    
    async loadInitialData() {
        try {
            // Load audio devices
            const response = await fetch('/api/audio/devices');
            const devices = await response.json();
            this.populateAudioDevices(devices);
            
            // Load system status
            const statusResponse = await fetch('/api/status');
            const status = await statusResponse.json();
            this.updateUI(status);
            
        } catch (error) {
            console.error('Failed to load initial data:', error);
        }
    }
    
    populateAudioDevices(devices) {
        const deviceSelect = document.getElementById('audio-device');
        if (!deviceSelect) return;
        
        deviceSelect.innerHTML = '<option value=\"\">Default Device</option>';
        
        Object.entries(devices).forEach(([id, device]) => {
            const option = document.createElement('option');
            option.value = id;
            option.textContent = `${device.name} (${device.channels} ch)`;
            deviceSelect.appendChild(option);
        });
    }
    
    updateUI(data) {
        if (!data) return;
        
        // Update audio info
        if (data.audio) {
            const deviceSelect = document.getElementById('audio-device');
            if (deviceSelect && data.audio.current_device !== null) {
                deviceSelect.value = data.audio.current_device.toString();
            }
            
            // Update MP3 status
            this.updateMP3Status(data.audio.mp3_status);
        }
        
        // Update LED info
        if (data.led) {
            const ledCount = document.getElementById('led-count');
            if (ledCount) ledCount.value = data.led.led_count;
            
            const brightness = document.getElementById('brightness');
            const brightnessValue = document.getElementById('brightness-value');
            if (brightness && data.led.brightness !== undefined) {
                brightness.value = data.led.brightness;
                if (brightnessValue) brightnessValue.textContent = data.led.brightness;
            }
            
            // Update performance stats
            this.updatePerformanceStats(data.led.performance);
        }
        
        // Update zones
        if (data.zones) {
            this.updateZonesDisplay(data.zones);
        }
        
        // Update presets
        if (data.presets) {
            this.updatePresetsDropdown(data.presets, data.current_preset);
        }
    }
    
    updateRealtimeData(data) {
        if (!data) return;
        
        // Update audio visualizer
        if (data.audio) {
            this.drawAudioVisualizer(data.audio);
            this.updateFrequencyBars(data.audio);
            
            // Update stats
            const audioRMS = document.getElementById('audio-rms');
            if (audioRMS) {
                audioRMS.textContent = (data.audio.rms * 100).toFixed(1) + '%';
            }
        }
        
        // Update LED visualizer
        if (data.zones) {
            this.drawLEDStrip(data.zones);
            
            const activeZones = document.getElementById('active-zones');
            if (activeZones) {
                const enabledZones = data.zones.filter(z => z.enabled).length;
                activeZones.textContent = enabledZones;
            }
        }
        
        // Update LED performance
        if (data.led && data.led.performance) {
            const ledFPS = document.getElementById('led-fps');
            if (ledFPS) {
                ledFPS.textContent = data.led.performance.fps?.toFixed(1) || '--';
            }
            
            const fpsDisplay = document.getElementById('fps-display');
            if (fpsDisplay) {
                fpsDisplay.textContent = `FPS: ${data.led.performance.fps?.toFixed(1) || '--'}`;
            }
        }
        
        // Update WLED status
        if (data.led && data.led.device_status) {
            const wledStatus = document.getElementById('wled-status');
            if (wledStatus) {
                const primaryDevice = data.led.device_status.find(d => d.is_primary);
                wledStatus.textContent = primaryDevice ? 
                    (primaryDevice.online ? 'Online' : 'Offline') : 'No Device';
                wledStatus.style.color = primaryDevice?.online ? '#4CAF50' : '#f44336';
            }
        }
    }
    
    drawAudioVisualizer(audioData) {
        if (!this.audioCtx || !audioData) return;
        
        const canvas = this.audioCanvas;
        const ctx = this.audioCtx;
        
        // Clear canvas
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw waveform representation
        const centerY = canvas.height / 2;
        const amplitude = audioData.rms * centerY * 2;
        
        ctx.strokeStyle = '#4CAF50';
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        // Simple sine wave based on audio data
        for (let x = 0; x < canvas.width; x++) {
            const frequency = 2 + audioData.peak * 5; // Frequency based on peak
            const y = centerY + Math.sin((x / canvas.width) * Math.PI * frequency) * amplitude;
            
            if (x === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
        
        // Add bass visualization
        if (audioData.bass > 0.1) {
            ctx.fillStyle = `rgba(76, 175, 80, ${audioData.bass})`;
            ctx.fillRect(0, canvas.height - audioData.bass * canvas.height, 
                        canvas.width, audioData.bass * canvas.height);
        }
    }
    
    updateFrequencyBars(audioData) {
        // Update frequency bar heights
        const bassBar = document.getElementById('bass-bar');
        const midsBar = document.getElementById('mids-bar');
        const rightsBar = document.getElementById('highs-bar');
        
        if (bassBar) bassBar.style.height = `${Math.min(100, audioData.bass * 100)}%`;
        if (midsBar) midsBar.style.height = `${Math.min(100, audioData.mids * 100)}%`;
        if (rightsBar) rightsBar.style.height = `${Math.min(100, audioData.highs * 100)}%`;
    }
    
    drawLEDStrip(zones) {
        if (!this.ledCtx || !zones) return;
        
        const canvas = this.ledCanvas;
        const ctx = this.ledCtx;
        
        // Clear canvas
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Calculate total LEDs from zones
        let totalLEDs = 30; // Default
        if (zones.length > 0) {
            totalLEDs = Math.max(...zones.map(z => z.end_led));
        }
        
        const ledWidth = canvas.width / totalLEDs;
        const ledHeight = canvas.height * 0.8;
        const offsetY = (canvas.height - ledHeight) / 2;
        
        // Draw each zone
        zones.forEach(zone => {
            if (!zone.enabled || !zone.colors) return;
            
            zone.colors.forEach((color, index) => {
                const ledIndex = zone.start_led + index;
                const x = ledIndex * ledWidth;
                
                // Draw LED
                ctx.fillStyle = `rgb(${color[0]}, ${color[1]}, ${color[2]})`;
                ctx.fillRect(x, offsetY, ledWidth - 1, ledHeight);
                
                // Add LED border
                if (color[0] + color[1] + color[2] > 50) {
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
                    ctx.lineWidth = 1;
                    ctx.strokeRect(x, offsetY, ledWidth - 1, ledHeight);
                }
            });
        });
    }
    
    // Event Handlers
    handleAudioSourceChange(event) {
        const source = event.target.value;
        const deviceSelection = document.getElementById('device-selection');
        const mp3Controls = document.getElementById('mp3-controls');
        
        if (source === 'mp3') {
            deviceSelection.style.display = 'none';
            mp3Controls.style.display = 'block';
        } else {
            deviceSelection.style.display = 'block';
            mp3Controls.style.display = 'none';
            
            // Update audio device setting
            const useSystemAudio = source === 'system';
            this.updateAudioDevice(null, useSystemAudio);
        }
    }
    
    handleAudioDeviceChange(event) {
        const deviceId = event.target.value ? parseInt(event.target.value) : null;
        const audioSource = document.getElementById('audio-source').value;
        const useSystemAudio = audioSource === 'system';
        
        this.updateAudioDevice(deviceId, useSystemAudio);
    }
    
    async updateAudioDevice(deviceId, useSystemAudio) {
        try {
            const response = await fetch('/api/audio/device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    device_id: deviceId,
                    use_system_audio: useSystemAudio
                })
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to update audio device');
            }
        } catch (error) {
            console.error('Error updating audio device:', error);
        }
    }
    
    handleMP3FileChange(event) {
        const file = event.target.files[0];
        if (file) {
            // In a real implementation, you'd upload the file to the server
            // For now, we'll just use the file path
            const filePath = file.name; // This won't work in practice
            this.setMP3Input(filePath);
        }
    }
    
    async setMP3Input(filePath) {
        try {
            const response = await fetch('/api/audio/mp3', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: filePath,
                    loop: true
                })
            });
            
            const result = await response.json();
            if (result.success) {
                console.log('MP3 input set successfully');
            }
        } catch (error) {
            console.error('Error setting MP3 input:', error);
        }
    }
    
    async controlMP3(action) {
        try {
            let body = { action };
            
            if (action === 'seek') {
                const seekSlider = document.getElementById('mp3-seek');
                body.position = parseFloat(seekSlider.value) / 100.0;
            }
            
            const response = await fetch('/api/audio/mp3/control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to control MP3');
            }
        } catch (error) {
            console.error('Error controlling MP3:', error);
        }
    }
    
    handleMP3Seek(event) {
        // Debounce seeking
        clearTimeout(this.seekTimeout);
        this.seekTimeout = setTimeout(() => {
            this.controlMP3('seek');
        }, 100);
    }
    
    updateMP3Status(status) {
        if (!status || !status.enabled) return;
        
        const mp3Seek = document.getElementById('mp3-seek');
        const mp3Time = document.getElementById('mp3-time');
        
        if (mp3Seek && !mp3Seek.matches(':active')) {
            mp3Seek.value = status.position * 100;
        }
        
        if (mp3Time) {
            const currentMin = Math.floor(status.current_time / 60);
            const currentSec = Math.floor(status.current_time % 60);
            const totalMin = Math.floor(status.duration / 60);
            const totalSec = Math.floor(status.duration % 60);
            
            mp3Time.textContent = 
                `${currentMin}:${currentSec.toString().padStart(2, '0')} / ` +
                `${totalMin}:${totalSec.toString().padStart(2, '0')}`;
        }
    }
    
    handleBrightnessChange(event) {
        const brightness = parseInt(event.target.value);
        const brightnessValue = document.getElementById('brightness-value');
        if (brightnessValue) {
            brightnessValue.textContent = brightness;
        }
        
        // Debounce LED config update
        clearTimeout(this.brightnessTimeout);
        this.brightnessTimeout = setTimeout(() => {
            this.updateLEDConfig({ brightness });
        }, 200);
    }
    
    handleLEDConfigChange() {
        const ledCount = parseInt(document.getElementById('led-count').value);
        const wledIP = document.getElementById('wled-ip').value;
        
        const config = {};
        if (ledCount) config.led_count = ledCount;
        if (wledIP) config.wled_ip = wledIP;
        
        this.updateLEDConfig(config);
    }
    
    async updateLEDConfig(config) {
        try {
            const response = await fetch('/api/led/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            if (!result.success) {
                console.error('Failed to update LED config');
            }
        } catch (error) {
            console.error('Error updating LED config:', error);
        }
    }
    
    testLEDs(pattern) {
        this.socket.emit('led_test', { pattern });
    }
    
    // Zone Management
    showAddZoneModal() {
        const modal = document.getElementById('add-zone-modal');
        if (modal) {
            modal.style.display = 'flex';
            modal.classList.add('fade-in');
        }
    }
    
    hideAddZoneModal() {
        const modal = document.getElementById('add-zone-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    }
    
    async saveZone() {
        const name = document.getElementById('zone-name').value;
        const startPercent = parseFloat(document.getElementById('zone-start').value) / 100;
        const endPercent = parseFloat(document.getElementById('zone-end').value) / 100;
        const frequencyRange = document.getElementById('zone-frequency').value;
        const effectType = document.getElementById('zone-effect').value;
        const sensitivity = parseFloat(document.getElementById('zone-sensitivity').value);
        
        if (!name || startPercent < 0 || endPercent <= startPercent || endPercent > 1) {
            alert('Please enter valid zone parameters');
            return;
        }
        
        try {
            const response = await fetch('/api/zones', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    start_percent: startPercent,
                    end_percent: endPercent,
                    frequency_range: frequencyRange,
                    effect_type: effectType,
                    sensitivity
                })
            });
            
            const result = await response.json();
            if (result.success) {
                this.hideAddZoneModal();
                this.socket.emit('request_status'); // Refresh zones
                
                // Clear form
                document.getElementById('zone-name').value = '';
                document.getElementById('zone-start').value = '0';
                document.getElementById('zone-end').value = '100';
                document.getElementById('zone-sensitivity').value = '1';
            }
        } catch (error) {
            console.error('Error saving zone:', error);
        }
    }
    
    async clearAllZones() {
        if (!confirm('Are you sure you want to clear all zones?')) return;
        
        // This would need an API endpoint to clear all zones
        // For now, we'll just refresh
        this.socket.emit('request_status');
    }
    
    updateZonesDisplay(zones) {
        const container = document.getElementById('zones-container');
        if (!container) return;
        
        container.innerHTML = '';
        
        zones.forEach(zone => {
            const zoneElement = this.createZoneElement(zone);
            container.appendChild(zoneElement);
        });
    }
    
    createZoneElement(zone) {
        const div = document.createElement('div');
        div.className = `zone-item ${zone.enabled ? 'zone-enabled' : 'zone-disabled'}`;
        
        div.innerHTML = `
            <div class=\"zone-header\">
                <div>
                    <div class=\"zone-name\">${zone.name}</div>
                    <div class=\"zone-range\">${(zone.start_percent * 100).toFixed(0)}% - ${(zone.end_percent * 100).toFixed(0)}% (LEDs ${zone.start_led}-${zone.end_led})</div>
                </div>
                <div class=\"zone-controls-inline\">
                    <button onclick=\"app.toggleZone('${zone.name}', ${!zone.enabled})\">${zone.enabled ? 'Disable' : 'Enable'}</button>
                    <button onclick=\"app.deleteZone('${zone.name}')\">Delete</button>
                </div>
            </div>
            <div class=\"zone-settings\">
                <div class=\"control-group\">
                    <label>Frequency:</label>
                    <select onchange=\"app.updateZoneEffect('${zone.name}', this)\">
                        <option value=\"all\" ${zone.frequency_range === 'all' ? 'selected' : ''}>All</option>
                        <option value=\"bass\" ${zone.frequency_range === 'bass' ? 'selected' : ''}>Bass</option>
                        <option value=\"mids\" ${zone.frequency_range === 'mids' ? 'selected' : ''}>Mids</option>
                        <option value=\"highs\" ${zone.frequency_range === 'highs' ? 'selected' : ''}>Highs</option>
                    </select>
                </div>
                <div class=\"control-group\">
                    <label>Effect:</label>
                    <select onchange=\"app.updateZoneEffect('${zone.name}', this)\">
                        <option value=\"spectrum\" ${zone.effect_type === 'spectrum' ? 'selected' : ''}>Spectrum</option>
                        <option value=\"flash\" ${zone.effect_type === 'flash' ? 'selected' : ''}>Flash</option>
                        <option value=\"color_change\" ${zone.effect_type === 'color_change' ? 'selected' : ''}>Color Change</option>
                        <option value=\"moving\" ${zone.effect_type === 'moving' ? 'selected' : ''}>Moving</option>
                        <option value=\"solid\" ${zone.effect_type === 'solid' ? 'selected' : ''}>Solid</option>
                        <option value=\"gradient\" ${zone.effect_type === 'gradient' ? 'selected' : ''}>Gradient</option>
                    </select>
                </div>
                <div class=\"control-group\">
                    <label>Sensitivity: <span>${zone.sensitivity}</span></label>
                    <input type=\"range\" min=\"0.1\" max=\"5\" step=\"0.1\" value=\"${zone.sensitivity}\" 
                           onchange=\"app.updateZoneSensitivity('${zone.name}', this.value); this.previousElementSibling.querySelector('span').textContent = this.value\">
                </div>
            </div>
        `;
        
        return div;
    }
    
    async toggleZone(name, enabled) {
        try {
            const response = await fetch(`/api/zones/${name}/enable`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            
            const result = await response.json();
            if (result.success) {
                this.socket.emit('request_status');
            }
        } catch (error) {
            console.error('Error toggling zone:', error);
        }
    }
    
    async deleteZone(name) {
        if (!confirm(`Delete zone '${name}'?`)) return;
        
        try {
            const response = await fetch(`/api/zones/${name}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            if (result.success) {
                this.socket.emit('request_status');
            }
        } catch (error) {
            console.error('Error deleting zone:', error);
        }
    }
    
    async updateZoneEffect(name, element) {
        // This would update the zone's frequency range or effect type
        // Implementation depends on which select was changed
        this.socket.emit('request_status');
    }
    
    async updateZoneSensitivity(name, sensitivity) {
        // Update zone sensitivity via WebSocket
        this.socket.emit('zone_update', {
            name,
            sensitivity: parseFloat(sensitivity)
        });
    }
    
    // Preset Management
    updatePresetsDropdown(presets, currentPreset) {
        const presetList = document.getElementById('preset-list');
        if (!presetList) return;
        
        presetList.innerHTML = '<option value=\"\">Select Preset...</option>';
        
        presets.forEach(preset => {
            const option = document.createElement('option');
            option.value = preset;
            option.textContent = preset;
            if (preset === currentPreset) {
                option.selected = true;
            }
            presetList.appendChild(option);
        });
    }
    
    async loadPreset() {
        const presetName = document.getElementById('preset-list').value;
        if (!presetName) return;
        
        try {
            const response = await fetch(`/api/presets/${presetName}`, {
                method: 'POST'
            });
            
            const result = await response.json();
            if (result.success) {
                this.socket.emit('request_status');
                alert(`Preset '${presetName}' loaded successfully`);
            }
        } catch (error) {
            console.error('Error loading preset:', error);
        }
    }
    
    async savePreset() {
        const presetName = document.getElementById('new-preset-name').value;
        if (!presetName) {
            alert('Please enter a preset name');
            return;
        }
        
        try {
            const response = await fetch(`/api/presets/${presetName}`, {
                method: 'PUT'
            });
            
            const result = await response.json();
            if (result.success) {
                document.getElementById('new-preset-name').value = '';
                this.socket.emit('request_status');
                alert(`Preset '${presetName}' saved successfully`);
            }
        } catch (error) {
            console.error('Error saving preset:', error);
        }
    }
    
    async safeShutdown() {
        if (!confirm('Are you sure you want to shutdown CircLights? This will stop the entire system.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/system/shutdown', {
                method: 'POST'
            });
            
            const result = await response.json();
            if (result.success) {
                alert('Shutdown initiated. CircLights will stop shortly.');
                // Update UI to show shutdown in progress
                this.updateConnectionStatus('Shutting down...', false);
            }
        } catch (error) {
            console.error('Error initiating shutdown:', error);
            alert('Failed to initiate shutdown. You may need to stop the program manually.');
        }
    }
    
    async testWLEDConnection() {
        const wledIP = document.getElementById('wled-ip').value;
        const statusElement = document.getElementById('wled-connection-status');
        const button = document.getElementById('test-wled-connection');
        
        if (!wledIP) {
            statusElement.textContent = 'Please enter an IP address';
            statusElement.className = 'connection-status error';
            return;
        }
        
        // Update UI to show testing
        button.disabled = true;
        button.textContent = 'Testing...';
        statusElement.textContent = 'Testing connection...';
        statusElement.className = 'connection-status testing';
        
        try {
            const response = await fetch('/api/led/test-connection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ wled_ip: wledIP })
            });
            
            const result = await response.json();
            
            if (result.success) {
                const device = result.device_info;
                statusElement.innerHTML = `✓ Connected: ${device.name} (${device.led_count} LEDs, v${device.version})`;
                statusElement.className = 'connection-status success';
                
                // Update LED count if returned by device
                const ledCountInput = document.getElementById('led-count');
                if (ledCountInput && device.led_count) {
                    ledCountInput.value = device.led_count;
                }
            } else {
                statusElement.textContent = `✗ Failed: ${result.error}`;
                statusElement.className = 'connection-status error';
            }
            
        } catch (error) {
            console.error('Error testing WLED connection:', error);
            statusElement.textContent = '✗ Connection test failed';
            statusElement.className = 'connection-status error';
        } finally {
            // Reset button
            button.disabled = false;
            button.textContent = 'Test Connection';
        }
    }
    
    updatePerformanceStats(performance) {
        // Performance stats are updated in updateRealtimeData
    }
    
    handleResize() {
        // Resize canvases
        if (this.audioCanvas) {
            this.audioCanvas.width = this.audioCanvas.offsetWidth;
            this.audioCanvas.height = this.audioCanvas.offsetHeight;
        }
        
        if (this.ledCanvas) {
            this.ledCanvas.width = this.ledCanvas.offsetWidth;
            this.ledCanvas.height = this.ledCanvas.offsetHeight;
        }
    }
}

// Initialize app when DOM is loaded
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new CircLightsApp();
});

// Make app globally available for inline event handlers
window.app = app;