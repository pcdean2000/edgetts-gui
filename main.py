import sys
import os

# 確保程式能夠正確讀取根目錄模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger
# 1. 必須在任何匯入 pydub/edge_tts 之前呼叫 setup_logger()，確保 Popen 被攔截
setup_logger()

from ui.main_window import TTSWizardUI

def main():
    # 2. 啟動 Modern UI 主程式
    app = TTSWizardUI()
    app.mainloop()

if __name__ == "__main__":
    main()
