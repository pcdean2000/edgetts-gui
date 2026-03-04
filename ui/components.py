import customtkinter as ctk
import logging

class VoiceSelectionPopup(ctk.CTkToplevel):
    def __init__(self, master, voices_by_lang, current_voice_short_name, on_voice_selected):
        super().__init__(master)
        self.title("Select Voice")
        self.transient(master)
        self.overrideredirect(True)
        
        self.voices_by_lang = voices_by_lang
        self.on_voice_selected = on_voice_selected
        
        self.bind("<FocusOut>", self._on_focus_out)
        self.bind("<Escape>", lambda e: self.destroy())
        
        btn = master.voice_selector_btn
        self.target_width = btn.winfo_width()
        if self.target_width < 320:
            self.target_width = 320 
            
        self.target_height = 380
        self.popup_x = btn.winfo_rootx()
        self.popup_y = btn.winfo_rooty() + btn.winfo_height() + 2
        
        self.geometry(f"{self.target_width}x0+{self.popup_x}+{self.popup_y}")
        
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        
        self.lang_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="#2b2b2b")
        self.lang_scroll.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        
        header_frame = ctk.CTkFrame(self.lang_scroll, fg_color="transparent")
        header_frame.pack(fill="x", pady=(5, 5))
        ctk.CTkLabel(header_frame, text="Select Language", font=ctk.CTkFont(size=16, weight="bold")).pack(side="left", padx=5)
        
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

        self.voices_container = ctk.CTkFrame(self.main_frame, fg_color="#1e1e1e")
        self.voices_container.place(relx=1.0, rely=0, relwidth=0.7, relheight=1.0)
        
        self.voices_scroll = ctk.CTkScrollableFrame(self.voices_container, fg_color="transparent")
        self.voices_scroll.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.animating = False
        
        self._animate_dropdown_open(0)
        # 不使用 focus_force 避免強制奪取焦點後，導致關閉時 Windows 無法將鍵盤歸還給主視窗
        self.after(150, self.focus_set)
        
        self._global_click_id = self.master.winfo_toplevel().bind("<Button-1>", self._on_global_click, add="+")

    def _on_global_click(self, event):
        try:
            x1 = self.winfo_rootx()
            y1 = self.winfo_rooty()
            x2 = x1 + self.winfo_width()
            y2 = y1 + self.winfo_height()
            
            if not (x1 <= event.x_root <= x2 and y1 <= event.y_root <= y2):
                self.after(10, self.destroy)
        except:
            pass

    def destroy(self):
        try:
            self.master.winfo_toplevel().unbind("<Button-1>", self._global_click_id)
        except:
            pass
        # 關閉選單時主動嘗試將焦點還給發起此選單的母視窗
        try:
            if hasattr(self.master, "text_input"):
                self.master.text_input.focus_set()
            else:
                self.master.focus_set()
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
            self._animate_slide(0.3, current_relx)

    def _animate_slide(self, target_relx, current_relx):
        step = -0.1 if target_relx < current_relx else 0.1
        new_relx = current_relx + step
        
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


class DeviceRowComponent(ctk.CTkFrame):
    """
    Component Pattern (元件模式) 的實體化。
    代表一條輸出設備選擇器（Combobox 搭配刪除按鈕），由上層父視窗管理集合與互動。
    """
    def __init__(self, master, device_names, preset_name, on_remove_callback, on_change_callback, show_remove_btn=True):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="x", pady=2)
        self.grid_columnconfigure(0, weight=1)
        
        self.on_remove = on_remove_callback
        self.on_change = on_change_callback
        
        self.combobox = ctk.CTkComboBox(
            self, 
            values=device_names,
            font=ctk.CTkFont(size=14),
            command=self._handle_change
        )
        self.combobox.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        
        if preset_name in device_names:
            self.combobox.set(preset_name)
        elif "Default" in device_names:
            self.combobox.set("Default")
            
        if show_remove_btn:
            self.remove_btn = ctk.CTkButton(
                self, 
                text="-", 
                width=30, 
                fg_color="#C0392B", 
                hover_color="#922B21",
                command=self._handle_remove
            )
            self.remove_btn.grid(row=0, column=1)

    def _handle_change(self, choice):
        self.on_change(self, choice)

    def _handle_remove(self):
        self.on_remove(self)

    def get_value(self):
        return self.combobox.get()
        
    def set_value(self, value):
        self.combobox.set(value)
        
    def update_options(self, options):
        self.combobox.configure(values=options)
