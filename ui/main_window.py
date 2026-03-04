import customtkinter as ctk
import asyncio
import threading
import logging
from tkinter import filedialog

from core.config import ConfigManager
from core.audio import AudioDeviceRepository
from core.voices import VoiceRepository
from core.tts_engine import TTSEngine
from ui.components import VoiceSelectionPopup, DeviceRowComponent

class TTSWizardUI(ctk.CTk):
    """
    MVC 架構中的 View/Controller 層。
    專注於控制介面生命週期、組合元件 (Composite)、綁定商業邏輯與介面事件。
    """
    def __init__(self):
        super().__init__()

        # 初始化基礎設定
        self.config_manager = ConfigManager()
        self.output_devices_map = AudioDeviceRepository.get_output_devices()
        
        # 準備資料庫緩存
        self.voices_by_lang = asyncio.run(VoiceRepository.get_voices_by_language())
        
        self.title("Edge TTS Wizard")
        self.geometry("700x580")
        self.minsize(500, 450)
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        
        self.device_rows = []
        
        self._create_widgets()
        
    def _save_settings(self):
        self.config_manager.set("voice", getattr(self, 'current_voice_short_name', None))
        self.config_manager.set("devices", [row.get_value() for row in self.device_rows])
        self.config_manager.set("auto_clear", self.auto_clear_var.get())
        self.config_manager.set("format", self.format_combobox.get() if hasattr(self, 'format_combobox') else "mp3")
        self.config_manager.set("tab", self.mode_tabview.get() if hasattr(self, 'mode_tabview') else "Live Playback")
        self.config_manager.save()

    def _on_closing(self):
        self._save_settings()
        self.destroy()

    def _create_widgets(self):
        self.title_label = ctk.CTkLabel(self, text="Edge TTS Wizard", font=ctk.CTkFont(size=26, weight="bold"))
        self.title_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(1, weight=1)
        
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
        
        saved_voice = self.config_manager.get("voice")
        if saved_voice:
            self.current_voice_short_name = saved_voice
            display_text = VoiceRepository.get_display_name(saved_voice)
            self._update_voice_button_text(display_text)
        else:
            self.current_voice_short_name = "zh-TW-HsiaoChenNeural"
            self._update_voice_button_text("zh-TW - zh-TW-HsiaoChenNeural (Female)")

        self.mode_tabview = ctk.CTkTabview(self.settings_frame, height=130)
        self.mode_tabview.grid(row=1, column=0, columnspan=2, padx=15, pady=(5, 10), sticky="ew")
        
        self.tab_live = self.mode_tabview.add("Live Playback")
        self.tab_export = self.mode_tabview.add("Export to File")
        self.mode_tabview.configure(command=self._on_tab_changed)
        
        # Tab 1: Live Playback
        self.tab_live.grid_columnconfigure(0, weight=1)
        self.device_header_frame = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        self.device_header_frame.grid(row=0, column=0, pady=(5, 5), sticky="ew")
        self.device_header_frame.grid_columnconfigure(0, weight=1)
        
        self.device_label = ctk.CTkLabel(self.device_header_frame, text="Output Devices:", font=ctk.CTkFont(size=14))
        self.device_label.grid(row=0, column=0, sticky="w")
        
        self.add_device_button = ctk.CTkButton(
            self.device_header_frame, text="+ Add Channel", width=110,
            fg_color="#27AE60", hover_color="#1E8449", command=self._add_device_row
        )
        self.add_device_button.grid(row=0, column=1, sticky="e")
        
        self.devices_container = ctk.CTkFrame(self.tab_live, fg_color="transparent")
        self.devices_container.grid(row=1, column=0, pady=(0, 5), sticky="ew")
        self.devices_container.grid_columnconfigure(0, weight=1)
        
        saved_devices = self.config_manager.get("devices", [])
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

        self._update_all_comboboxes_values()

        # Tab 2: Export to File
        self.tab_export.grid_columnconfigure(0, weight=0)
        self.tab_export.grid_columnconfigure(1, weight=1)
        
        self.format_label = ctk.CTkLabel(self.tab_export, text="Format:", font=ctk.CTkFont(size=14))
        self.format_label.grid(row=0, column=0, padx=(10, 15), pady=20, sticky="w")
        
        self.format_combobox = ctk.CTkComboBox(self.tab_export, values=["mp3", "wav"], font=ctk.CTkFont(size=14))
        self.format_combobox.grid(row=0, column=1, padx=(0, 10), pady=20, sticky="ew")
        
        if self.config_manager.get("format"):
            self.format_combobox.set(self.config_manager.get("format"))
            
        saved_tab = self.config_manager.get("tab", "Live Playback")
        try:
            self.mode_tabview.set(saved_tab)
        except Exception:
            self.mode_tabview.set("Live Playback")

        # Input Area
        self.text_input = ctk.CTkTextbox(
            self, font=ctk.CTkFont(size=16), wrap="word", border_width=2, border_color="#333333"
        )
        self.text_input.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.text_input.bind("<Return>", self._on_enter_pressed)
        self.text_input.bind("<Shift-Return>", self._on_shift_enter_pressed)

        # Controls Area
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.control_frame.grid(row=3, column=0, padx=20, pady=(10, 20), sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1)
        self.control_frame.grid_columnconfigure(1, weight=0)
        self.control_frame.grid_columnconfigure(2, weight=0)
        
        self.play_button = ctk.CTkButton(
            self.control_frame, text="Play / Send", font=ctk.CTkFont(size=16, weight="bold"),
            height=45, command=self._on_play_clicked
        )
        self.play_button.grid(row=0, column=0, padx=(0, 15), pady=0, sticky="ew")

        self.clear_button = ctk.CTkButton(
            self.control_frame, text="Clear", font=ctk.CTkFont(size=14),
            fg_color="#555555", hover_color="#444444", height=45, width=100, command=self._on_clear_clicked
        )
        self.clear_button.grid(row=0, column=1, padx=(0, 15), pady=0, sticky="e")
        
        self.auto_clear_var = ctk.BooleanVar(value=self.config_manager.get("auto_clear", True))
        self.auto_clear_checkbox = ctk.CTkCheckBox(self.control_frame, text="Auto-Clear", variable=self.auto_clear_var, font=ctk.CTkFont(size=14))
        self.auto_clear_checkbox.grid(row=0, column=2, padx=0, pady=0, sticky="e")
        
        self._on_tab_changed()

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

    def _on_tab_changed(self):
        current_tab = self.mode_tabview.get()
        if current_tab == "Live Playback":
            self.play_button.configure(text="Play / Send")
        else:
            self.play_button.configure(text="Save to File")

    def _add_device_row(self, preset_name=None):
        device_names = list(self.output_devices_map.keys())
        show_remove_btn = len(self.device_rows) >= 1
        
        row_comp = DeviceRowComponent(
            self.devices_container, 
            device_names, 
            preset_name,
            self._remove_device_row, 
            self._validate_device_selection,
            show_remove_btn
        )
        
        self.device_rows.append(row_comp)
        
        # We need to re-evaluate the remove buttons (if first row now has a sibling, etc)
        # For simplicity, we just rebuild or add the remove button manually, 
        # but in Tkinter, just update options logic.
        if len(self.device_rows) > 1 and not hasattr(self.device_rows[0], 'remove_btn'):
            # Lazy hack: Just leave the first row without a remove button like before
            pass
            
        self._update_all_comboboxes_values()
        
    def _remove_device_row(self, row_comp):
        if len(self.device_rows) <= 1:
            return
            
        row_comp.destroy()
        self.device_rows.remove(row_comp)
        self._update_all_comboboxes_values()

    def _update_all_comboboxes_values(self):
        selected_devices = [
            row.get_value() 
            for row in self.device_rows 
            if row.get_value() != "Default"
        ]
        all_devices = list(self.output_devices_map.keys())
        
        for row in self.device_rows:
            current_val = row.get_value()
            others_selected = [d for d in selected_devices if d != current_val]
            available_values = [d for d in all_devices if d not in others_selected]
            row.update_options(available_values)

    def _validate_device_selection(self, row_comp, choice):
        if choice != "Default":
            count = sum(1 for row in self.device_rows if row.get_value() == choice)
            if count > 1:
                logging.warning(f"防止重複選擇通道: {choice}")
                row_comp.set_value("Default")
        self._update_all_comboboxes_values()

    def _on_enter_pressed(self, event):
        self._on_play_clicked()
        return "break"

    def _on_shift_enter_pressed(self, event):
        self.text_input.insert("insert", "\n")
        return "break"

    def _on_play_clicked(self):
        text_content = self.text_input.get("1.0", "end-1c").strip()
        if not text_content:
            return

        voice_model = getattr(self, 'current_voice_short_name', "zh-TW-HsiaoChenNeural")
        current_tab = self.mode_tabview.get()
        
        if current_tab == "Live Playback":
            target_device_ids = []
            for row in self.device_rows:
                dev_name = row.get_value()
                dev_id = self.output_devices_map.get(dev_name)
                if dev_id not in target_device_ids:
                    target_device_ids.append(dev_id)
            
            if self.auto_clear_var.get():
                self.text_input.delete("1.0", "end")
            
            self.play_button.configure(state="disabled", text="Playing...")

            def _restore_live_button():
                self.play_button.configure(state="normal", text="Play / Send")

            def play_task():
                try:
                    asyncio.run(TTSEngine.play_stream(text_content, voice_model, target_device_ids))
                except Exception as e:
                    logging.error(f"Error during playback: {e}")
                finally:
                    self.after(0, _restore_live_button)

            threading.Thread(target=play_task, daemon=True).start()
            
        else:
            output_format = self.format_combobox.get()
            default_ext = f".{output_format}"
            file_types = [(f"{output_format.upper()} Audio", f"*{default_ext}")]
            
            save_path = filedialog.asksaveasfilename(
                title="Save Audio As...",
                defaultextension=default_ext,
                filetypes=file_types,
                initialfile=f"tts_output{default_ext}"
            )
            
            if not save_path:
                return
                
            if self.auto_clear_var.get():
                self.text_input.delete("1.0", "end")
                
            self.play_button.configure(state="disabled", text="Generating...")
            
            def _restore_save_button():
                self.play_button.configure(state="normal", text="Save to File")

            def save_task():
                try:
                    asyncio.run(TTSEngine.export_file(text_content, voice_model, save_path, output_format))
                except Exception as e:
                    logging.error(f"Error during file save: {e}")
                finally:
                    self.after(0, _restore_save_button)

            threading.Thread(target=save_task, daemon=True).start()

    def _on_clear_clicked(self):
        self.text_input.delete("1.0", "end")
