import edge_tts
import logging
import asyncio

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

class VoiceRepository:
    """
    Repository Pattern (儲存庫模式) 實作。
    專責向 Edge-TTS 獲取模型資料，並緩存 (Cache) 資料，進行預處理。
    """
    _cache_voices_by_lang = None

    @classmethod
    async def get_voices_by_language(cls) -> dict:
        """
        異步獲取所有語音模型並照著語言字典分群。
        回傳結構: {"English": [{"display": "...", "short_name": "..."}, ...]}
        """
        if cls._cache_voices_by_lang is not None:
            return cls._cache_voices_by_lang

        voices_by_lang = {}
        try:
            voices_raw = await edge_tts.list_voices()
            for voice in voices_raw:
                short_name = voice['ShortName']
                locale = voice['Locale']
                gender = voice['Gender']
                
                clean_name = short_name.replace(f"{locale}-", "").replace("Neural", "")
                display_name = f"{locale} - {clean_name} ({gender})"
                base_lang = get_language_name(locale)
                
                if base_lang not in voices_by_lang:
                    voices_by_lang[base_lang] = []
                    
                voices_by_lang[base_lang].append({
                    'display': display_name,
                    'short_name': short_name,
                    'locale': locale
                })
            
            cls._cache_voices_by_lang = voices_by_lang
            return voices_by_lang
            
        except Exception as e:
            logging.error(f"Failed to fetch voices: {e}")
            # 發生網路錯誤時的回退機制
            fallback = {'Chinese': [{'display': 'zh-TW - zh-TW-HsiaoChenNeural (Female)', 'short_name': 'zh-TW-HsiaoChenNeural', 'locale': 'zh-TW'}]}
            return fallback

    @classmethod
    def get_display_name(cls, search_short_name: str) -> str:
        """根據 short_name 查找對應的前端顯示名稱"""
        if not cls._cache_voices_by_lang:
            return search_short_name
            
        for lang_list in cls._cache_voices_by_lang.values():
            for v in lang_list:
                if v['short_name'] == search_short_name:
                    return v['display']
        return search_short_name
