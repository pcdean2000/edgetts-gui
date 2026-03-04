import subprocess
import sys
import logging
import os

def setup_logger():
    """初始化 logging 機制並修改 Windows 下的 subprocess 行為，避免 ffmpeg 彈出黑框"""
    
    # 1. 初始化 Logging
    logging.basicConfig(
        filename='tts.log',
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )
    
    if sys.platform == "win32":
        class PatchedPopen(subprocess.Popen):
            def __init__(self, *args, **kwargs):
                # 注入 CREATE_NO_WINDOW flag (0x08000000)
                if 'creationflags' not in kwargs:
                    kwargs['creationflags'] = 0x08000000
                else:
                    kwargs['creationflags'] |= 0x08000000
                    
                if 'stdout' not in kwargs:
                    kwargs['stdout'] = subprocess.DEVNULL
                if 'stderr' not in kwargs:
                    kwargs['stderr'] = subprocess.DEVNULL
                    
                super().__init__(*args, **kwargs)

        subprocess.Popen = PatchedPopen

    # 3. Dynamic FFmpeg Path for PyInstaller --onefile
    from pydub import AudioSegment
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        AudioSegment.converter = os.path.join(base_path, "ffmpeg.exe")
        os.environ["PATH"] += os.pathsep + base_path
