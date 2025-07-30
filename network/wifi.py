import subprocess
import time
import logging

class WiFiManager:
    """WiFi connection management using nmcli"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def connect(self, ssid, auth="OPEN", username="", password=""):
        """
        Connect to WiFi network with specified authentication
        
        Args:
            ssid (str): Network SSID
            auth (str): Authentication type - "OPEN", "WPA2_PSK", "EAP_PEAP", "EAP_TTLS"
            username (str): Username for enterprise networks
            password (str): Password
            
        Returns:
            dict: {"status": "success/failure", "message": "description"}
        """
        try:
            # Validate parameters
            validation_result = self._validate_params(ssid, auth, username, password)
            if validation_result["status"] != "success":
                return validation_result
            
            # Scan for available networks before attempting connection
            scan_result = self._scan_networks()
            if not self._is_network_available(ssid, scan_result):
                return {"status": "failure", "message": f"Network '{ssid}' not found in scan results"}
            
            # Delete existing connection
            self._delete_existing_connection(ssid)
            
            # Connect based on auth type
            if auth == "OPEN":
                return self._connect_open(ssid)
            elif auth == "WPA2_PSK":
                return self._connect_wpa2_psk(ssid, password)
            elif auth == "EAP_PEAP":
                return self._connect_eap_peap(ssid, username, password)
            elif auth == "EAP_TTLS":
                return self._connect_eap_ttls(ssid, username, password)
            else:
                return {"status": "failure", "message": f"Unsupported auth type: {auth}"}
                
        except Exception as e:
            self.logger.error(f"WiFi connection error: {e}")
            return {"status": "failure", "message": str(e)}
    
    def _validate_params(self, ssid, auth, username, password):
        """Validate connection parameters"""
        if not ssid:
            return {"status": "failure", "message": "SSID is required"}
        
        if auth in ["WPA2_PSK"] and not password:
            return {"status": "failure", "message": "Password required for WPA2_PSK"}
        
        if auth in ["EAP_PEAP", "EAP_TTLS"] and (not username or not password):
            return {"status": "failure", "message": "Username and password required for enterprise networks"}
        
        return {"status": "success", "message": "Parameters valid"}
    
    def _delete_existing_connection(self, ssid):
        """Delete existing connection with same SSID"""
        try:
            subprocess.run(
                ["nmcli", "connection", "delete", ssid],
                capture_output=True, text=True, check=False
            )
        except Exception:
            pass  # Ignore errors if connection doesn't exist
    
    def _scan_networks(self):
        """Scan for available WiFi networks"""
        try:
            self.logger.info("Scanning for available WiFi networks...")
            result = subprocess.run(
                ["nmcli", "device", "wifi", "rescan"],
                capture_output=True, text=True, check=False
            )
            
            # Wait a moment for scan to complete
            time.sleep(2)
            
            # Get the scan results
            scan_result = subprocess.run(
                ["nmcli", "device", "wifi", "list"],
                capture_output=True, text=True, check=True
            )
            
            self.logger.info("Network scan completed")
            return scan_result.stdout
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to scan networks: {e}")
            return ""
        except Exception as e:
            self.logger.error(f"Network scan error: {e}")
            return ""
    
    def _is_network_available(self, ssid, scan_output):
        """Check if network is available in scan results"""
        if not scan_output:
            return False
        
        # Check if SSID appears in scan output
        for line in scan_output.split('\n'):
            if ssid in line:
                self.logger.info(f"Network '{ssid}' found in scan results")
                return True
        
        self.logger.warning(f"Network '{ssid}' not found in scan results")
        return False
    
    def _connect_open(self, ssid):
        """Connect to open network"""
        cmd = ["nmcli", "device", "wifi", "connect", ssid]
        return self._execute_connection(cmd, ssid)
    
    def _connect_wpa2_psk(self, ssid, password):
        """Connect to WPA2 Personal network"""
        cmd = ["nmcli", "device", "wifi", "connect", ssid, "password", password]
        return self._execute_connection(cmd, ssid)
    
    def _connect_eap_peap(self, ssid, username, password):
        """Connect to EAP-PEAP enterprise network"""
        # Create connection profile
        cmd_create = [
            "nmcli", "connection", "add",
            "type", "wifi",
            "con-name", ssid,
            "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-eap",
            "802-1x.eap", "peap",
            "802-1x.phase2-auth", "mschapv2",
            "802-1x.identity", username,
            "802-1x.password", password
        ]
        
        result = subprocess.run(cmd_create, capture_output=True, text=True)
        if result.returncode != 0:
            return {"status": "failure", "message": f"Failed to create PEAP profile: {result.stderr}"}
        
        # Activate connection
        cmd_activate = ["nmcli", "connection", "up", ssid]
        return self._execute_connection(cmd_activate, ssid, is_activation=True)
    
    def _connect_eap_ttls(self, ssid, username, password):
        """Connect to EAP-TTLS enterprise network"""
        # Create connection profile
        cmd_create = [
            "nmcli", "connection", "add",
            "type", "wifi",
            "con-name", ssid,
            "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-eap",
            "802-1x.eap", "ttls",
            "802-1x.phase2-auth", "pap",
            "802-1x.identity", username,
            "802-1x.password", password
        ]
        
        result = subprocess.run(cmd_create, capture_output=True, text=True)
        if result.returncode != 0:
            return {"status": "failure", "message": f"Failed to create TTLS profile: {result.stderr}"}
        
        # Activate connection
        cmd_activate = ["nmcli", "connection", "up", ssid]
        return self._execute_connection(cmd_activate, ssid, is_activation=True)
    
    def _execute_connection(self, cmd, ssid, is_activation=False):
        """Execute connection command and verify"""
        try:
            self.logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                # Verify connection
                if self._verify_connection(ssid):
                    return {"status": "success", "message": f"Successfully connected to {ssid}"}
                else:
                    return {"status": "failure", "message": f"Connection to {ssid} not verified"}
            else:
                return {"status": "failure", "message": f"Connection failed: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"status": "failure", "message": f"Connection timeout for {ssid}"}
    
    def _verify_connection(self, ssid):
        """Verify that connection is active"""
        try:
            time.sleep(3)  # Wait for connection to stabilize
            result = subprocess.run(
                ["nmcli", "connection", "show", "--active"],
                capture_output=True, text=True, check=True
            )
            return ssid in result.stdout
        except Exception:
            return False
    
    def get_status(self):
        """Get current WiFi status and available networks"""
        try:
            # Scan for available networks to get fresh results
            networks_output = self._scan_networks()
            
            # Get active connections
            active_result = subprocess.run(
                ["nmcli", "connection", "show", "--active"],
                capture_output=True, text=True, check=True
            )
            
            # Parse active WiFi connections
            active_wifi = []
            for line in active_result.stdout.split('\n')[1:]:
                if line.strip() and 'wifi' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        active_wifi.append(parts[0])
            
            return {
                "status": "success",
                "available_networks": networks_output,
                "active_connections": active_wifi
            }
            
        except subprocess.CalledProcessError as e:
            return {"status": "failure", "message": str(e)}
    
    def disconnect(self, ssid):
        """Disconnect from specific network"""
        try:
            result = subprocess.run(
                ["nmcli", "connection", "down", ssid],
                capture_output=True, text=True, check=True
            )
            return {"status": "success", "message": f"Disconnected from {ssid}"}
        except subprocess.CalledProcessError as e:
            return {"status": "failure", "message": str(e)}