

import io, wave
import os, json, sys
import threading
from uuid import uuid4
from typing import List, Dict
import urllib.parse
import hashlib

now_dir = os.getcwd()
sys.path.append(now_dir)
# sys.path.append(os.path.join(now_dir, "GPT_SoVITS"))

from Inference.src.config_manager import load_infer_config, auto_generate_infer_config, inference_config, get_device_info, get_deflaut_character_name, params_config, update_character_info
models_path = inference_config.models_path
disabled_features = inference_config.disabled_features

dict_language = {
    "中文": "all_zh",#全部按中文识别
    "英文": "en",#全部按英文识别#######不变
    "日文": "all_ja",#全部按日文识别
    "中英混合": "zh",#按中英混合识别####不变
    "日英混合": "ja",#按日英混合识别####不变
    "多语种混合": "auto",#多语种启动切分识别语种
    "auto": "auto",
    "zh": "zh",
    "en": "en",
    "ja": "ja",
    "all_zh": "all_zh",
    "all_ja": "all_ja",
}

from GPT_SoVITS.TTS_infer_pack.TTS import TTS, TTS_Config

class TTS_Task:
    def __init__(self, other_task=None):
        self.text = ""
        self.uuid = str(uuid4())
        self.audio_path = ""
        
        self.emotion = params_config["emotion"]["default"] if other_task is None else other_task.emotion
        self.loudness = params_config["loudness"]["default"] if other_task is None else other_task.loudness
        self.text_language = params_config["text_language"]["default"] if other_task is None else other_task.text_language
        self.character = params_config["character"]["default"] if other_task is None else other_task.character
        self.speaker_id = params_config["speaker_id"]["default"] if other_task is None else other_task.speaker_id
        self.batch_size = params_config["batch_size"]["default"] if other_task is None else other_task.batch_size
        self.speed = params_config["speed"]["default"] if other_task is None else other_task.speed
        self.top_k = params_config["top_k"]["default"] if other_task is None else other_task.top_k
        self.top_p = params_config["top_p"]["default"] if other_task is None else other_task.top_p
        self.temperature = params_config["temperature"]["default"] if other_task is None else other_task.temperature
        self.cut_method = params_config["cut_method"]["default"] if other_task is None else other_task.cut_method
        self.format = params_config["format"]["default"] if other_task is None else other_task.format
        self.save_temp = params_config["save_temp"]["default"] if other_task is None else other_task.save_temp
        self.stream = params_config["stream"]["default"] if other_task is None else other_task.stream
    
    def get_param_value(self, param_name, data, return_default=True, special_dict={}):
        # ban disabled features
        param_config = params_config[param_name]
        if param_name not in disabled_features:
            for alias in param_config['alias']:
                if data.get(alias) is not None:
                    if special_dict.get(data.get(alias)) is not None:
                        return special_dict[data.get(alias)]
                    elif param_config['type'] == 'int':
                        return int(data.get(alias))
                    elif param_config['type'] == 'float':
                        x = data.get(alias)
                        if isinstance(x, str) and x[-1] == "%":
                            return float(x[:-1]) / 100
                        return float(x)
                    elif param_config['type'] == 'bool':
                        return str(data.get(alias)).lower() in ('true', '1', 't', 'y', 'yes', "allow", "allowed")
                    else:  # 默认为字符串
                        return urllib.parse.unquote(data.get(alias))
        if return_default:
            return param_config['default']
        else:
            return None
        
    def update_from_param(self, param_name, data, special_dict={}):
        value = self.get_param_value(param_name, data, return_default=False, special_dict=special_dict)
        if value is not None:
            setattr(self, param_name, value)
    
    def load_from_dict(self, data: dict={}):
        
        assert params_config is not None, "params_config.json not found."
        # 参数提取
        self.text = self.get_param_value('text', data).strip()
        
        self.character = self.get_param_value('character', data)
        self.speaker_id = self.get_param_value('speaker_id', data)

        self.text_language = self.get_param_value('text_language', data)
        self.batch_size = self.get_param_value('batch_size', data)
        self.speed = self.get_param_value('speed', data)
        self.top_k = self.get_param_value('top_k', data)
        self.top_p = self.get_param_value('top_p', data)
        self.temperature = self.get_param_value('temperature', data)
        self.seed = self.get_param_value('seed', data)
        
        self.cut_method = self.get_param_value('cut_method', data)
        self.format = self.get_param_value('format', data)
        self.stream = self.get_param_value('stream', data)
        self.emotion = self.get_param_value('emotion', data)
        
        if self.cut_method == "auto_cut":
            self.cut_method = f"auto_cut_100"
        
    def md5(self):
        m = hashlib.md5()
        m.update(self.text.encode())
        m.update(self.text_language.encode())
        m.update(self.character.encode())
        m.update(str(self.speaker_id).encode())
        m.update(str(self.speed).encode())
        m.update(str(self.top_k).encode())
        m.update(str(self.top_p).encode())
        m.update(str(self.temperature).encode())
        m.update(str(self.cut_method).encode())
        m.update(str(self.emotion).encode())
        return m.hexdigest()
            
    def to_dict(self):
        return {
            "text": self.text,
            "text_language": self.text_language,
            "character_emotion": self.emotion,
            "batch_size": self.batch_size,
            "speed": self.speed,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "cut_method": self.cut_method,
            "format": self.format,
        }
        
    def __str__(self):
        character = self.character
        json_content = json.dumps(self.to_dict(), ensure_ascii=False)  # ensure_ascii=False to properly display non-ASCII characters
        return f"----------------TTS Task--------------\ncharacter: {character}, content: {json_content}\n--------------------------------------"

class TTS_instance:
    def __init__(self, character_name = None):
        tts_config = TTS_Config("")
        tts_config.device , tts_config.is_half = get_device_info()
        self.tts_pipline = TTS(tts_config)
        if character_name is None:
            character_name = get_deflaut_character_name()
        self.character = None
        self.lock = threading.Lock()
        self.load_character(character_name)
        
        
    def inference(self, text, text_language, 
              ref_audio_path, prompt_text, 
              prompt_lang, top_k, 
              top_p, temperature, 
              text_split_method, batch_size, 
              speed_factor, ref_text_free,
              split_bucket,
              return_fragment,
              seed
              ):
    
        inputs={
            "text": text,
            "text_lang": text_language,
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text if not ref_text_free else "",
            "prompt_lang": prompt_lang,
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "text_split_method": text_split_method,
            "batch_size":int(batch_size),
            "speed_factor":float(speed_factor),
            "split_bucket":split_bucket,
            "return_fragment":return_fragment,
            "seed":seed
        }
        return self.tts_pipline.run(inputs)

    # from https://github.com/RVC-Boss/GPT-SoVITS/pull/448
    def get_streaming_tts_wav(self, params):
        # from https://huggingface.co/spaces/coqui/voice-chat-with-mistral/blob/main/app.py
        def wave_header_chunk(frame_input=b"", channels=1, sample_width=2, sample_rate=32000):
            wav_buf = io.BytesIO()
            with wave.open(wav_buf, "wb") as vfout:
                vfout.setnchannels(channels)
                vfout.setsampwidth(sample_width)
                vfout.setframerate(sample_rate)
                vfout.writeframes(frame_input)

            wav_buf.seek(0)
            return wav_buf.read()
        chunks = self.tts_pipline.run(params)
        yield wave_header_chunk()
        for sr, chunk in chunks:
            if chunk is not None:
                chunk = chunk.tobytes()
                yield chunk
            else:
                print("None chunk")
                pass
    
    def load_character_id(self, speaker_id):
        character = list(update_character_info()['characters_and_emotions'])[speaker_id]
        return self.load_character(character)
    
    def load_character(self, character):
        if character in ["", None] and self.character in ["", None]:
            character = get_deflaut_character_name()
        if self.character not in ["", None]:
            if type(character) != str:
                raise Exception(f"The type of character name should be str, but got {type(character)}")
            if self.character.lower() == character.lower():
                return
        character_path=os.path.join(models_path, character)
        if not os.path.exists(character_path):
            print(f"找不到角色文件夹: {character}，已自动切换到默认角色")
            character = get_deflaut_character_name()
            return self.load_character(character)
            # raise Exception(f"Can't find character folder: {character}")
        try:
            # 加载配置
            config = load_infer_config(character_path)
            
            # 尝试从环境变量获取gpt_path，如果未设置，则从配置文件读取
            gpt_path = os.path.join(character_path,config.get("gpt_path"))
            # 尝试从环境变量获取sovits_path，如果未设置，则从配置文件读取
            sovits_path = os.path.join(character_path,config.get("sovits_path"))
        except:
            try:
                # 尝试调用auto_get_infer_config
                auto_generate_infer_config(character_path)
                self.load_character(character)
                return 
            except:
                # 报错
                raise Exception("找不到模型文件！请把有效模型放置在模型文件夹下，确保其中至少有pth、ckpt和wav三种文件。")
        # 修改权重
        self.character = character
        with self.lock:
            self.tts_pipline.init_t2s_weights(gpt_path)
            self.tts_pipline.init_vits_weights(sovits_path)
            print(f"加载角色成功: {character}")


    def match_character_emotion(self, character_path):
        if not os.path.exists(os.path.join(character_path, "reference_audio")):
            # 如果没有reference_audio文件夹，就返回None
            return None, None, None

    def get_wav_from_task(self, task: TTS_Task):
        character = task.character
        self.load_character(character)
        return self.get_wav_from_text_api(**task.to_dict())
        
    def get_wav_from_text_api(
        self,
        text,
        text_language="auto",
        batch_size=1,
        speed=1.0,
        top_k=12,
        top_p=0.6,
        temperature=0.6,
        character_emotion="default",
        cut_method="auto_cut",
        seed=-1,
        stream=False,
        **kwargs
    ):
        
        text = text.replace("\r", "\n").replace("<br>", "\n").replace("\t", " ")
        text = text.replace("……","。").replace("…","。").replace("\n\n","\n").replace("。\n","\n").replace("\n", "。\n")
        # 加载环境配置
        config = load_infer_config(os.path.join(models_path, self.character))

        # 尝试从配置中提取参数，如果找不到则设置为None
        ref_wav_path =  None
        prompt_text = None
        prompt_language = None
        if character_emotion == "auto":
            # 如果是auto模式，那么就自动决定情感
            ref_wav_path, prompt_text, prompt_language = self.match_character_emotion(os.path.join(models_path, self.character))
        if ref_wav_path is None:
            # 未能通过auto匹配到情感，就尝试使用指定的情绪列表
            emotion_list=config.get('emotion_list', None)# 这是新版的infer_config文件，如果出现错误请删除infer_config.json文件，让系统自动生成 
            now_emotion="default"
            for emotion, details in emotion_list.items():
                print(emotion)
                if emotion==character_emotion:
                    now_emotion=character_emotion
                    break
            for emotion, details in emotion_list.items():
                if emotion==now_emotion:
                    ref_wav_path = os.path.join(os.path.join(models_path,self.character), details['ref_wav_path'])
                    prompt_text = details['prompt_text']
                    prompt_language = details['prompt_language']
                    break
            if ref_wav_path is None:
                print("找不到ref_wav_path！请删除infer_config.json文件，让系统自动生成")

        try:
            text_language = dict_language[text_language]
            prompt_language = dict_language[prompt_language]
            if "-" in text_language:
                text_language = text_language.split("-")[0]
            if "-" in prompt_language:
                prompt_language = prompt_language.split("-")[0]
        except:
            text_language = "auto"
            prompt_language = "auto"
        ref_free = False
        
        params = {
            "text": text,
            "text_lang": text_language.lower(),
            "ref_audio_path": ref_wav_path,
            "prompt_text": prompt_text,
            "prompt_lang": prompt_language.lower(),
            "top_k": top_k,
            "top_p": top_p,
            "temperature": temperature,
            "text_split_method": cut_method, 
            "batch_size": batch_size,
            "speed_factor": speed,
            "ref_text_free": ref_free,
            "split_bucket":True,
            "return_fragment":stream,
            "seed": seed,
        }
        # 调用原始的get_tts_wav函数
        # 注意：这里假设get_tts_wav函数及其所需的其它依赖已经定义并可用
        with self.lock:
            if stream == False:
                return self.tts_pipline.run(params)
            else:
                return self.get_streaming_tts_wav(params)


