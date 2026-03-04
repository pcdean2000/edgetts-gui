import sounddevice as sd

class AudioDeviceRepository:
    """
    Repository Pattern (儲存庫模式) 的實作。
    負責與作業系統底層 API 溝通，獲取並過濾出可用的輸出設備清單。
    """
    @staticmethod
    def get_output_devices() -> dict:
        """
        獲取系統可用的音訊輸出設備。
        回傳結構: {"設備名稱 (ID: x)": 設備ID}
        包含一個特定的 {"Default": None} 通用選項。
        """
        devices = sd.query_devices()
        output_devices = {}
        
        # 手動加入預設設備
        output_devices['Default'] = None
        
        hostapi = sd.default.hostapi
        
        for idx, device in enumerate(devices):
            if device['hostapi'] != hostapi:
                continue
                
            if device['max_output_channels'] > 0:
                name_lower = device['name'].lower()
                
                # 排除純麥克風，但保留包含 cable/virtual 的虛擬音源線
                if '麥克風' in name_lower or 'microphone' in name_lower:
                    if 'cable' not in name_lower and 'virtual' not in name_lower:
                        continue
                
                name = f"{device['name']} (ID: {idx})"
                output_devices[name] = idx
                
        return output_devices
