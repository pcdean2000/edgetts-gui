import customtkinter as ctk
import sounddevice as sd
import threading
import queue
import time
import os
import asyncio
import edge_tts
import logging
import json
import os

from tts import stream_and_play, generate_and_save
from tkinter import filedialog

SETTINGS_FILE = "tts_settings.json"

LOCALE_MAP = {
    'af': 'Afrikaans', 'am': 'Amharic', 'ar': 'Arabic', 'az': 'Azerbaijani',
    'bg': 'Bulgarian', 'bn': 'Bengali', 'bs': 'Bosnian', 'ca': 'Catalan',
    'cs': 'Czech', 'cy': 'Welsh', 'da': 'Danish', 'de': 'German',
    'el': 'Greek', 'en': 'English', 'es': 'Spanish', 'et': 'Estonian',
    'fa': 'Persian', 'fi': 'Finnish', 'fr': 'French', 'ga': 'Irish',
    'gl': 'Galician', 'gu': 'Gujarati', 'he': 'Hebrew', 'hi': 'Hindi',
    'hr': 'Croatian', 'hu': 'Hungarian', 'id': 'Indonesian', 'is': 'Icelandic',
    'it': 'Italian', 'ja': 'Japanese', 'jv': 'Javanese', 'ka': 'Georgian',
    'kk': 'Kazakh', 'km': 'Khmer', 'kn': 'Kannada', 'ko': 'Korean',
    'lo': 'Lao', 'lt': 'Lithuanian', 'lv': 'Latvian', 'mk': 'Macedonian',
    'ml': 'Malayalam', 'mn': 'Mongolian', 'mr': 'Marathi', 'ms': 'Malay',
    'mt': 'Maltese', 'my': 'Burmese', 'nb': 'Norwegian Bokmål', 'ne': 'Nepali',
    'nl': 'Dutch', 'pl': 'Polish', 'ps': 'Pashto', 'pt': 'Portuguese',
    'ro': 'Romanian', 'ru': 'Russian', 'si': 'Sinhala', 'sk': 'Slovak',
    'sl': 'Slovenian', 'so': 'Somali', 'sq': 'Albanian', 'sr': 'Serbian',
    'su': 'Sundanese', 'sv': 'Swedish', 'sw': 'Swahili', 'ta': 'Tamil',
    'te': 'Telugu', 'th': 'Thai', 'tr': 'Turkish', 'uk': 'Ukrainian',
    'ur': 'Urdu', 'uz': 'Uzbek', 'vi': 'Vietnamese', 'zh': 'Chinese',
    'zu': 'Zulu'
}

def get_language_name(locale_code):
    lang_prefix = locale_code.split('-')[0]
    return LOCALE_MAP.get(lang_prefix, lang_prefix.upper())

def get_audio_devices():
    """獲取系統可用的音訊輸出設備，回傳 {設備名稱: 設備ID} 字典"""
    devices = sd.query_devices()
    output_devices = {}
    
    # 手動加入預設設備
    output_devices['Default'] = None
    
    hostapi = sd.default.hostapi
    
    for idx, device in enumerate(devices):
        # 1. 只針對預設 API，避免重複抓取
        if device['hostapi'] != hostapi:
            continue
            
        # 2. 只要最大輸出聲道大於 0，就視為輸出設備
        if device['max_output_channels'] > 0:
            name_lower = device['name'].lower()
            
            # 3. 排除純輸入的麥克風 (但保留包含 cable 的虛擬音源線)
            if '麥克風' in name_lower or 'microphone' in name_lower:
                if 'cable' not in name_lower:
                    continue
            
            # 加入 ID 確保名稱唯一性，並方便使用者辨識
            name = f"{device['name']} (ID: {idx})"
            output_devices[name] = idx
            
    return output_devices

class VoiceSelectionPopup(ctk.CTkToplevel):
    def __init__(self, master, voices_by_lang, current_voice_short_name, on_voice_selected):
        super().__init__(master)
        self.title("Select Voice")
        self.transient(master)
        self.overrideredirect(True)
        
        self.voices_by_lang = voices_by_lang
        self.on_voice_selected = on_voice_selected
        
        # 綁定焦點失去與 Esc 關閉事件
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda e: self.destroy())
        
        # 取得母視窗按鈕的位置與大小，用於定位拉下選單
        btn = master.voice_selector_btn
        self.target_width = btn.winfo_width()
        if self.target_width < 320:
            self.target_width = 320  # 設定最小寬度防呆
            
        self.target_height = 380
        self.popup_x = btn.winfo_rootx()
        self.popup_y = btn.winfo_rooty() + btn.winfo_height() + 2
        
        # 初始高度為 0 以做下滑動畫
        self.geometry(f"{self.target_width}x0+{self.popup_x}+{self.popup_y}")
        
        # 滿版的背景框架，用來裁剪裡頭滑動的元件
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        
        # 第一層：大語系 (100% 寬度)
        self.lang_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="#2b2b2b")
        self.lang_scroll.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        
        header_frame = ctk.CTkFrame(self.lang_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(5, 5))
        ctk.CTkLabel(header_frame, text="Select Language", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=5)
        # 用戶可以使用外部點擊或 ESC 關閉，不用特別放 X 按鈕
        
        for lang in sorted(self.voices_by_lang.keys()):
            btn_lang = ctk.CTkButton(
                self.lang_scroll, 
                text=lang,
                fg_color="transparent",
                hover_color="#444444",
                anchor="w",
                command=lambda l=lang: self._show_voices_for_lang(l)
            )
            btn_lang.pack(fill="x", pady=2, padx=5)

        # 第二層容器：發音員選單
        # 使用 70% 寬度，滑入時左側會保留 30% 原本的語系選單
        self.voices_container = ctk.CTkFrame(self.main_frame, fg_color="#1e1e1e")
        self.voices_container.place(relx=1.0, rely=0, relwidth=0.7, relheight=1.0)
        
        self.voices_scroll = ctk.CTkScrollableFrame(self.voices_container, fg_color="transparent")
        self.voices_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.animating = False
        
        # 動畫展開與強制作為焦點以確保 Esc 鍵能夠每次被觸發
        self._animate_dropdown_open(0)
        self.after(150, self.focus_force)
        
        # 不使用 grab_set() 避免 Alt-Tab 時 Windows 焦點混亂
        # 改透過全應用程式層級的滑鼠點擊攔截來實作「點選外圍關閉」
        self._global_click_id = self.master.winfo_toplevel().bind("<Button-1>", self._on_global_click, add="+")

    def _on_global_click(self, event):
        # 檢查滑鼠游標是否落在 popup 選單範圍以外
        try:
            x1 = self.winfo_rootx()
            y1 = self.winfo_rooty()
            x2 = x1 + self.winfo_width()
            y2 = y1 + self.winfo_height()
            
            # 若點選區域在選單外部，關閉選單
            if not (x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2):
                # 延遲關閉，讓被點擊的元件(如Textbox)可以先吃下這一次的點擊事件並拿到焦點
                self.after(10, self.destroy)
        except:
            pass

    def destroy(self):
        # 解除全域滑鼠監聽
        try:
            self.master.winfo_toplevel().unbind("<Button-1>", self._global_click_id)
        except:
            pass
        super().destroy()

    def _animate_dropdown_open(self, current_h):
        new_h = current_h + 40
        if new_h >= self.target_height:
            self.geometry(f"{self.target_width}x{self.target_height}+{self.popup_x}+{self.popup_y}")
        else:
            self.geometry(f"{self.target_width}x{new_h}+{self.popup_x}+{self.popup_y}")
            self.after(10, self._animate_dropdown_open, new_h)

    def _on_focus_out(self, event):
        self.after(50, self._check_focus)
        
    def _check_focus(self):
        try:
            focused = self.focus_get()
            if focused is None or focused.winfo_toplevel() != self:
                self.destroy()
        except:
            self.destroy()

    def _show_voices_for_lang(self, lang):
        for widget in self.voices_scroll.winfo_children():
            widget.destroy()
            
        header = ctk.CTkFrame(self.voices_scroll, fg_color="transparent")
        header.pack(fill="x", pady=(0, 5))
        
        ctk.CTkButton(header, text="< Back", width=60, fg_color="#555555", hover_color="#444444", command=self._hide_voices).pack(side="left")
        ctk.CTkLabel(header, text=f"{lang} Voices", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=15)
        
        for voice_dict in self.voices_by_lang[lang]:
            btn = ctk.CTkButton(
                self.voices_scroll,
                text=voice_dict['display'],
                fg_color="transparent",
                hover_color="#2980B9",
                anchor="w",
                command=lambda v=voice_dict: self._select_voice(v)
            )
            btn.pack(fill="x", pady=2)
            
        current_relx = float(self.voices_container.place_info()['relx'])
        if current_relx > 0.3 and not self.animating:
            self.animating = True
            # 此將子選單拉進畫面並保留原本左邊30%
            self._animate_slide(0.3, current_relx)

    def _animate_slide(self, target_relx, current_relx):
        step = -0.1 if target_relx < current_relx else 0.1
        new_relx = current_relx + step
        
        # 修正浮點數誤差
        if (step < 0 and new_relx <= target_relx) or (step > 0 and new_relx >= target_relx):
            self.voices_container.place(relx=target_relx)
            self.animating = False
        else:
            self.voices_container.place(relx=new_relx)
            self.after(10, self._animate_slide, target_relx, new_relx)

    def _hide_voices(self):
        if not self.animating:
            self.animating = True
            current_relx = float(self.voices_container.place_info()['relx'])
            self._animate_slide(1.0, current_relx)

    def _select_voice(self, voice_dict):
        self.on_voice_selected(voice_dict)
        self.destroy()

class TTSWizardUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 視窗基本設定 ---
        self.title("Edge TTS Wizard")
        self.geometry("700x580")
        self.minsize(500, 450)
        
        # 攔截視窗關閉事件，儲存設定
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        # 設定為深色主題
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # --- 主視窗網格佈局權重設定 ---
        self.grid_columnconfigure(0, weight=1)
        # 讓 text_input 的 row (也就是 row=2) 隨視窗放大而延展
        self.grid_rowconfigure(2, weight=1)

        # 抓取所有 Edge-TTS 語音模型並依語系分群
        self.voices_by_lang = {}
        try:
            voices_raw = asyncio.run(edge_tts.list_voices())
            for voice in voices_raw:
                short_name = voice['ShortName']
                locale = voice['Locale']
                gender = voice['Gender']
                
                # 清除重複前綴與 Neural 字尾
                clean_name = short_name.replace(f"{locale}-", "").replace("Neural", "")
                display_name = f"{locale} - {clean_name} ({gender})"
                base_lang = get_language_name(locale)
                
                if base_lang not in self.voices_by_lang:
                    self.voices_by_lang[base_lang] = []
                    
                self.voices_by_lang[base_lang].append({
                    'display': display_name,
                    'short_name': short_name,
                    'locale': locale
                })
        except Exception as e:
            logging.error(f"Failed to fetch voices: {e}")
            self.voices_by_lang = {'Chinese': [{'display': 'zh-TW - zh-TW-HsiaoChenNeural (Female)', 'short_name': 'zh-TW-HsiaoChenNeural', 'locale': 'zh-TW'}]}
            
        # 讀取先前的設定檔
        self._load_settings()
        
        # 獲取音訊設備列表字典 {name: id}
        self.output_devices_map = get_audio_devices()

        # 用來儲存所有的 (combobox, row_frame) 參考，以便後續收集資料和刪除
        self.device_rows = []

        # 建立所有 UI 元件
        self._create_widgets()
        
    def _load_settings(self):
        self.saved_settings = {"voice": None, "devices": [], "auto_clear": True, "format": "mp3", "tab": "Live Playback"}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    self.saved_settings = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load settings: {e}")
                
    def _save_settings(self):
        try:
            settings = {
                "voice": getattr(self, 'current_voice_short_name', None),
                "devices": [combo.get() for combo, _ in self.device_rows],
                "auto_clear": self.auto_clear_var.get(),
                "format": self.format_combobox.get() if hasattr(self, 'format_combobox') else "mp3",
                "tab": self.mode_tabview.get() if hasattr(self, 'mode_tabview') else "Live Playback"
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logging.error(f"Failed to save settings: {e}")

    def _on_closing(self):
        self._save_settings()
        self.destroy()

    def _create_widgets(self):
        # ==========================================
        # 1. 頂部區域：標題標籤
        # ==========================================
        self.title_label = ctk.CTkLabel(
            self, 
            text="Edge TTS Wizard", 
            font=ctk.CTkFont(size=26, weight="bold")
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        # ==========================================
        # 2. 設定區域：包含 Voice Model 和 Output Device
        # ==========================================
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(1, weight=1)  # 讓下拉式選單佔滿剩餘空間
        
        # --- Voice Selector Button ---
        self.voice_label = ctk.CTkLabel(self.settings_frame, text="Voice Model:", font=ctk.CTkFont(size=14))
        self.voice_label.grid(row=0, column=0, padx=15, pady=(20, 10), sticky="nw")
        
        self.voice_selector_btn = ctk.CTkButton(
            self.settings_frame,
            text="Loading Voices...",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2C3E50",
            hover_color="#34495E",
            height=40,
            command=self._open_voice_selector
        )
        self.voice_selector_btn.grid(row=0, column=1, padx=15, pady=(15, 10), sticky="ew")
        
        # 載入儲存的語音模型設定，或使用預設
        if self.saved_settings.get("voice"):
            self.current_voice_short_name = self.saved_settings["voice"]
            display_text = self.current_voice_short_name
            for lang_list in self.voices_by_lang.values():
                for v in lang_list:
                    if v['short_name'] == self.current_voice_short_name:
                        display_text = v['display']
                        break
            self._update_voice_button_text(display_text)
        else:
            self.current_voice_short_name = "zh-TW-HsiaoChenNeural"
            self._update_voice_button_text("zh-TW - zh-TW-HsiaoChenNeural (Female)")

        # --- Modes Tabview (Live / Export) ---
        self.mode_tabview = ctk.CTkTabview(self.settings_frame, height=130)
        self.mode_tabview.grid(row=1, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="ew")
        
        self.tab_live = self.mode_tabview.add("Live Playback")
        self.tab_export = self.mode_tabview.add("Export to File")
        
        # 綁定切換事件來更改底部按鈕文字
        self.mode_tabview.configure(command=self._on_tab_changed)
        
        # ==========================================
        # Tab 1: Live Playback 內容
        # ==========================================
        self.tab_live.grid_columnconfigure(0, weight=1)

        # --- Output Devices Header (Label + Add Button) ---
        self.device_header_frame = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        self.device_header_frame.grid(row=0, column=0, pady=(5, 5), sticky="ew")
        self.device_header_frame.grid_columnconfigure(0, weight=1)
        
        self.device_label = ctk.CTkLabel(self.device_header_frame, text="Output Devices:", font=ctk.CTkFont(size=14))
        self.device_label.grid(row=0, column=0, sticky="w")
        
        self.add_device_button = ctk.CTkButton(
            self.device_header_frame, 
            text="+ Add Channel", 
            width=110,
            fg_color="#27AE60",
            hover_color="#1E8449",
            command=self._add_device_row
        )
        self.add_device_button.grid(row=0, column=1, sticky="e")
        
        # --- Output Devices Container (動態擴充區) ---
        self.devices_container = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        self.devices_container.grid(row=1, column=0, pady=(0, 5), sticky="ew")
        self.devices_container.grid_columnconfigure(0, weight=1) # 讓內部的選單延展
        
        # 初始化時載入儲存的設備，如果沒有紀錄就預設加入一行
        saved_devices = self.saved_settings.get("devices", [])
        
        # 任務一/二：過濾出系統確實存在的設備 (避免遺漏設備全部變成 Default)，並且清除多餘的重複實體通道
        valid_devices = []
        for dev_name in saved_devices:
            if dev_name in self.output_devices_map:
                if dev_name == "Default" or dev_name not in valid_devices:
                    valid_devices.append(dev_name)
                    
        if valid_devices:
            for dev_name in valid_devices:
                self._add_device_row(preset_name=dev_name)
        else:
            self._add_device_row()

        # 全部加入後，統一計算並隱藏各自被佔用的設備項目
        self._update_all_comboboxes_values()

        # ==========================================
        # Tab 2: Export to File 內容
        # ==========================================
        self.tab_export.grid_columnconfigure(0, weight=0)
        self.tab_export.grid_columnconfigure(1, weight=1)
        
        self.format_label = ctk.CTkLabel(self.tab_export, text="Format:", font=ctk.CTkFont(size=14))
        self.format_label.grid(row=0, column=0, padx=(10, 15), pady=20, sticky="w")
        
        self.format_combobox = ctk.CTkComboBox(
            self.tab_export, 
            values=["mp3", "wav"],
            font=ctk.CTkFont(size=14)
        )
        self.format_combobox.grid(row=0, column=1, padx=(0, 10), pady=20, sticky="ew")
        
        # 從設定還原
        if self.saved_settings.get("format"):
            self.format_combobox.set(self.saved_settings["format"])
            
        # 還原頁籤與按鈕文字狀態
        saved_tab = self.saved_settings.get("tab", "Live Playback")
        try:
            self.mode_tabview.set(saved_tab)
        except Exception:
            self.mode_tabview.set("Live Playback")

        # ==========================================
        # 3. 輸入區域：文字輸入框
        # ==========================================
        self.text_input = ctk.CTkTextbox(
            self, 
            font=ctk.CTkFont(size=16),
            wrap="word", # 自動換行
            border_width=2,
            border_color="#333333"
        )
        self.text_input.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        
        # 綁定鍵盤事件
        self.text_input.bind("<Return>", self._on_enter_pressed)
        self.text_input.bind("<Shift-Return>", self._on_shift_enter_pressed)

        # ==========================================
        # 4. 底部控制區：Play / Send 和 Clear 按鈕
        # ==========================================
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1) # 讓 Play 按鈕寬大一點
        self.control_frame.grid_columnconfigure(1, weight=0)
        self.control_frame.grid_columnconfigure(2, weight=0)
        
        # --- Play / Send 按鈕 ---
        self.play_button = ctk.CTkButton(
            self.control_frame, 
            text="Play / Send", 
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            command=self._on_play_clicked
        )
        # 給予右邊一點 padding 以隔開 Clear 按鈕
        self.play_button.grid(row=0, column=0, padx=(0, 15), pady=0, sticky="ew")

        # --- Clear 按鈕 ---
        self.clear_button = ctk.CTkButton(
            self.control_frame, 
            text="Clear", 
            font=ctk.CTkFont(size=14),
            fg_color="#555555",
            hover_color="#444444",
            height=45,
            width=100,
            command=self._on_clear_clicked
        )
        self.clear_button.grid(row=0, column=1, padx=(0, 15), pady=0, sticky="e")
        
        # --- Auto-Clear Checkbox ---
        self.auto_clear_var = ctk.BooleanVar(value=self.saved_settings.get("auto_clear", True))
        self.auto_clear_checkbox = ctk.CTkCheckBox(
            self.control_frame,
            text="Auto-Clear",
            variable=self.auto_clear_var,
            font=ctk.CTkFont(size=14)
        )
        self.auto_clear_checkbox.grid(row=0, column=2, padx=0, pady=0, sticky="e")
        
        # 更新初始按鈕文字
        self._on_tab_changed()

    # ==========================================
    # Voice Selector 事件
    # ==========================================
    def _update_voice_button_text(self, display_text):
        self.voice_selector_btn.configure(text=f"🎙 {display_text}")

    def _open_voice_selector(self):
        if hasattr(self, 'voice_popup') and self.voice_popup.winfo_exists():
            return
        self.voice_popup = VoiceSelectionPopup(self, self.voices_by_lang, getattr(self, 'current_voice_short_name', None), self._on_voice_selected)
        
    def _on_voice_selected(self, voice_dict):
        self.current_voice_short_name = voice_dict['short_name']
        self._update_voice_button_text(voice_dict['display'])
        self._save_settings()

    # ==========================================
    # Tab 切換事件
    # ==========================================
    def _on_tab_changed(self):
        current_tab = self.mode_tabview.get()
        if current_tab == "Live Playback":
            self.play_button.configure(text="Play / Send")
        else:
            self.play_button.configure(text="Save to File")

    # ==========================================
    # 動態設備選單區塊方法
    # ==========================================
    def _add_device_row(self, preset_name=None):
        row_frame = ctk.CTkFrame(self.devices_container, fg_color="transparent")
        row_frame.pack(fill="x", pady=2)
        row_frame.grid_columnconfigure(0, weight=1)
        
        device_names = list(self.output_devices_map.keys())
        
        combobox = ctk.CTkComboBox(
            row_frame, 
            values=device_names,
            font=ctk.CTkFont(size=14),
            command=lambda choice: self._validate_device_selection(choice, row_frame)
        )
        combobox.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        # 設定預設選項為傳入的名稱 (若存在於可用名單中)，否則退回 Default
        if preset_name in device_names:
            combobox.set(preset_name)
        elif "Default" in device_names:
            combobox.set("Default")
            
        self.device_rows.append((combobox, row_frame))
        
        # 如果不是第一行，就加上紅色的 '-' 移除按鈕
        if len(self.device_rows) > 1:
            remove_btn = ctk.CTkButton(
                row_frame, 
                text="-", 
                width=30, 
                fg_color="#C0392B", 
                hover_color="#922B21",
                command=lambda f=row_frame, c=combobox: self._remove_device_row(f, c)
            )
            remove_btn.grid(row=0, column=1)
            
        # 因應新增通道，更新其他人的下拉選單
        self._update_all_comboboxes_values()
        
    def _remove_device_row(self, row_frame, combobox):
        # 至少保留一個設備選單
        if len(self.device_rows) <= 1:
            return
            
        row_frame.destroy()
        self.device_rows.remove((combobox, row_frame))
        
        # 某個通道被刪除後，釋出設備，更新其他人的下拉選單
        self._update_all_comboboxes_values()

    def _update_all_comboboxes_values(self):
        """動態隱藏已經被其他通道選走的設備名稱"""
        # 收集目前所有已經被選取的實體設備 (Default 不限制)
        selected_devices = [
            combo.get() 
            for combo, _ in self.device_rows 
            if combo.get() != "Default"
        ]
        all_devices = list(self.output_devices_map.keys())
        
        # 逐一更新每個 combobox 內可顯示的下拉選單
        for combo, _ in self.device_rows:
            current_val = combo.get()
            # 別人選走的設備
            others_selected = [d for d in selected_devices if d != current_val]
            # 把別人選走的過濾掉
            available_values = [d for d in all_devices if d not in others_selected]
            combo.configure(values=available_values)

    def _validate_device_selection(self, choice, current_row_frame):
        # 檢查是否有重複選取的通道
        # 如果是 Default 則允許重複 (因為 Default 可能有各種實務上的意義，或者我們也可以限制 Default)
        # 但通常實體通道不該被重複選取
        if choice != "Default":
            count = 0
            current_combobox = None
            for combo, r_frame in self.device_rows:
                if r_frame == current_row_frame:
                    current_combobox = combo
                if combo.get() == choice:
                    count += 1
                    
            # 如果這個通道已經被超過一個人選上了，就將當前這個改回 Default，防呆退回
            if count > 1 and current_combobox is not None:
                logging.warning(f"防止重複選擇通道: {choice}")
                current_combobox.set("Default")
            
        # 每次選擇改變後，就觸發一波選單更新機制，避免同一個設備在別人的選單浮現
        self._update_all_comboboxes_values()

    # ==========================================
    # 鍵盤事件綁定
    # ==========================================
    def _on_enter_pressed(self, event):
        self._on_play_clicked()
        return "break"  # 阻止預設的換行行為

    def _on_shift_enter_pressed(self, event):
        self.text_input.insert("insert", "\n")
        return "break"  # 阻止換行並手動插入

    # ==========================================
    # 按鈕事件綁定
    # ==========================================
    def _on_play_clicked(self):
        text_content = self.text_input.get("1.0", "end-1c").strip()
        
        # 防呆設計：如果有空字串就不執行
        if not text_content:
            return

        voice_model = getattr(self, 'current_voice_short_name', "zh-TW-HsiaoChenNeural")
        current_tab = self.mode_tabview.get()
        
        # 根據不同的 Tab 執行不同邏輯
        if current_tab == "Live Playback":
            # 收集畫面上所有的設備下拉選單，轉換為 Device ID 列表 (並去除重複的 ID)
            target_device_ids = []
            for combo, _ in self.device_rows:
                dev_name = combo.get()
                dev_id = self.output_devices_map.get(dev_name)
                
                if dev_id not in target_device_ids:
                    target_device_ids.append(dev_id)
            
            # Auto-Clear 判斷與清空
            if self.auto_clear_var.get():
                self.text_input.delete("1.0", "end")
            
            # 1. 禁用按鈕 (防止重複點擊)，並更改文字提示
            self.play_button.configure(state="disabled", text="Playing...")

            # 定義還原按鈕的回呼函式
            def _restore_live_button():
                self.play_button.configure(state="normal", text="Play / Send")

            # 定義背景執行緒的工作
            def play_task():
                try:
                    logging.info(f"=== 按鈕被點擊: Play / Send ===")
                    logging.info(f"Voice Model: {voice_model}")
                    logging.info(f"Input Text: {text_content}")
                    logging.info(f"準備播放多重設備: {target_device_ids}")
                    asyncio.run(stream_and_play(text_content, voice_model, target_device_ids))
                    logging.info("==============================\n")
                except Exception as e:
                    logging.error(f"Error during playback: {e}")
                finally:
                    self.after(0, _restore_live_button)

            thread = threading.Thread(target=play_task, daemon=True)
            thread.start()
            
        else:
            # 存檔 (Export to File) 邏輯
            output_format = self.format_combobox.get()
            default_ext = f".{output_format}"
            file_types = [(f"{output_format.upper()} Audio", f"*{default_ext}")]
            
            # 使用 filedialog 取得儲存路徑
            save_path = filedialog.asksaveasfilename(
                title="Save Audio As...",
                defaultextension=default_ext,
                filetypes=file_types,
                initialfile=f"tts_output{default_ext}"
            )
            
            if not save_path:
                return # 使用者取消儲存
                
            # Auto-Clear 判斷與清空
            if self.auto_clear_var.get():
                self.text_input.delete("1.0", "end")
                
            # 禁用按鈕
            self.play_button.configure(state="disabled", text="Generating...")
            
            def _restore_save_button():
                self.play_button.configure(state="normal", text="Save to File")

            def save_task():
                try:
                    logging.info(f"=== 按鈕被點擊: Save to File ===")
                    logging.info(f"Voice Model: {voice_model}")
                    logging.info(f"Input Text: {text_content}")
                    logging.info(f"Output Path: {save_path}")
                    asyncio.run(generate_and_save(text_content, voice_model, save_path, output_format))
                    logging.info("==============================\n")
                except Exception as e:
                    logging.error(f"Error during file save: {e}")
                finally:
                    self.after(0, _restore_save_button)

            thread = threading.Thread(target=save_task, daemon=True)
            thread.start()

    def _on_clear_clicked(self):
        logging.info("=== 按鈕被點擊: Clear ===")
        self.text_input.delete("1.0", "end")


if __name__ == "__main__":
    app = TTSWizardUI()
    app.mainloop()
