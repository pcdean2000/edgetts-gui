import io
import logging
import asyncio
import threading
import queue
import re
import numpy as np
import sounddevice as sd
from pydub import AudioSegment
import edge_tts

class TTSEngine:
    """
    Facade Pattern (外觀模式) 實作。
    將複雜的非同步網路串流、本地端多執行緒播放佇列 (Queue) 以及 FFmpeg 解碼封裝在此。
    向主程式提供最乾淨的 API： `play_stream()` 與 `export_file()`
    """

    @staticmethod
    def _split_text_by_punctuation(text):
        """將長文本依照句號、驚嘆號等主要標點進行斷句，避免過度切分而導致語氣斷層"""
        chunks = re.split(r'([。！？；\n.!?]+)', text)
        sentences = []
        for i in range(0, len(chunks)-1, 2):
            sentence = (chunks[i] + chunks[i+1]).strip()
            if sentence:
                sentences.append(sentence)
        if len(chunks) % 2 != 0 and chunks[-1].strip():
            sentences.append(chunks[-1].strip())
        
        if not sentences and text.strip():
            return [text.strip()]
        return sentences

    @classmethod
    async def play_stream(cls, text, voice_model, target_device_ids=None):
        if not target_device_ids:
            target_device_ids = [None]
            
        sentences = cls._split_text_by_punctuation(text)
        if not sentences:
            return
            
        logging.info(f"開始管線化生成語音，文本共分為 {len(sentences)} 句")
        
        # 建立一個播放佇列 (Queue)，負責接收解碼好的音訊資料
        play_queue = queue.Queue()
        
        # [消費者] 播放執行緒：從 Queue 中拿聲音並同步播放到所有通道
        def playback_worker():
            while True:
                item = play_queue.get()
                if item is None: # None 是結束訊號
                    play_queue.task_done()
                    break
                    
                samples, frame_rate = item
                
                def play_on_device(dev_id):
                    try:
                        sd.play(samples, samplerate=frame_rate, device=dev_id)
                        sd.wait() # 阻斷這個子執行緒直到本句播放完畢
                    except Exception as e:
                        logging.error(f"在設備 ID {dev_id} 上播放時發生錯誤: {e}")
                        
                threads = []
                for dev_id in target_device_ids:
                    t = threading.Thread(target=play_on_device, args=(dev_id,))
                    threads.append(t)
                    t.start()
                    
                # 等待當前這個「句子」在所有設備上都播放完畢，才去 Queue 拿下一句
                for t in threads:
                    t.join()
                    
                play_queue.task_done()

        consumer_thread = threading.Thread(target=playback_worker, daemon=True)
        consumer_thread.start()
        
        # [生產者] 生成與解碼：一段一段生成音訊並塞入 Queue 以達成無縫銜接
        try:
            for idx, sentence in enumerate(sentences):
                logging.info(f"正在背景生成第 {idx+1}/{len(sentences)} 句: {sentence}")
                communicate = edge_tts.Communicate(sentence, voice_model)
                
                audio_data = b""
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_data += chunk["data"]
                        
                if not audio_data:
                    continue
                    
                # 將 bytes 資料轉為 pydub 的 AudioSegment 進行記憶體內解碼
                audio_io = io.BytesIO(audio_data)
                audio_segment = AudioSegment.from_file(audio_io, format="mp3")
                
                # 轉換為 sounddevice 可以播放的 numpy 陣列
                samples = np.array(audio_segment.get_array_of_samples())
                if audio_segment.channels == 2:
                    samples = samples.reshape((-1, 2))
                    
                # 生成好一句，丟進隊列排隊播放！
                play_queue.put((samples, audio_segment.frame_rate))
        finally:
            # 當所有句子都產生完畢後，發送結束信號給播放執行緒
            play_queue.put(None)
            
        # 主執行緒等待消費者全部播放完畢才退出
        consumer_thread.join()
        logging.info("所有通道管線化播放結束！")

    @classmethod
    async def export_file(cls, text, voice_model, output_path, output_format="mp3"):
        sentences = cls._split_text_by_punctuation(text)
        if not sentences:
            return
            
        logging.info(f"開始生成語音並準備匯出，文本共分為 {len(sentences)} 句")
        combined_audio = AudioSegment.empty()
        
        for idx, sentence in enumerate(sentences):
            logging.info(f"正在背景生成第 {idx+1}/{len(sentences)} 句: {sentence}")
            communicate = edge_tts.Communicate(sentence, voice_model)
            
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
                    
            if not audio_data:
                continue
                
            # 解碼這句的 MP3 並串接到完整音軌中
            audio_io = io.BytesIO(audio_data)
            segment = AudioSegment.from_file(audio_io, format="mp3")
            combined_audio += segment
            
        # 匯出檔案
        logging.info(f"語音生成與串接完成，正在儲存為 {output_format} 格式至: {output_path}")
        combined_audio.export(output_path, format=output_format)
        logging.info("檔案儲存成功！")
