import base64
import hashlib
import hmac
import json
import os
import ssl
import threading
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time

import torch
import websocket
from diffusers import StableDiffusionPipeline, AutoencoderKL, UNet2DConditionModel
from openai import OpenAI
from transformers import CLIPTextModel, CLIPTokenizer

API_KEY = "1"
API_BASE = "http://maas-api.cn-huabei-1.xf-yun.com/v1"
TTS_APPID = "1"
TTS_APISecret = "1"
TTS_APIKey = "1"


def llm(prompt: str, llm_name: str="Qwen") -> str:

    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    match llm_name:
        case "DeepSeek":
            model_id = "xopdeepseekv32"
        case "Qwen":
            model_id = "xop3qwen1b7"
        case _:
            pass
    messages = prompt
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=False,
            temperature=0.7,
            max_tokens=4096,
        )
        message = response.choices[0].message
        return message.content
    except Exception as e:
        print(f"{e}")
        raise e


class Ws_Param(object):
    # 初始化时接收 vcn (发音人)
    def __init__(self, APPID, APIKey, APISecret, Text, vcn):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text
        # 公共参数
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数：注意 vcn 动态传入
        self.BusinessArgs = {
            "aue": "lame",
            "sfl": 1,
            "auf": "audio/L16;rate=16000",
            "vcn": vcn,
            "tte": "utf8",
        }
        # 数据参数
        self.Data = {
            "status": 2,
            "text": str(base64.b64encode(self.Text.encode("utf-8")), "UTF8"),
        }

    def create_url(self):
        url = "wss://tts-api.xfyun.cn/v2/tts"
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = (
            "host: "
            + "ws-api.xfyun.cn"
            + "\n"
            + "date: "
            + date
            + "\n"
            + "GET "
            + "/v2/tts "
            + "HTTP/1.1"
        )
        signature_sha = hmac.new(
            self.APISecret.encode("utf-8"),
            signature_origin.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding="utf-8")
        authorization_origin = (
            'api_key="%s", algorithm="%s", headers="%s", signature="%s"'
            % (self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode(
            encoding="utf-8"
        )
        v = {"authorization": authorization, "date": date, "host": "ws-api.xfyun.cn"}
        return url + "?" + urlencode(v)


def tts(text: str, voice_role: str = "narrator", path: str = "."):
    #print(voice_role)
    VOICE_MAP = {
        "narrator": "x4_yezi",  # 旁白/解说
        "young_man": "aisjiuxu",  # 年轻男性
        "young_woman": "aisjinger",  # 年轻女性
        "old_woamn": "x4_xiaoyan",  # 老年女性
        "cute_boy": "aisbabyxu",  # 小男孩
        "女": "x4_lingxiaolu_en",
        "男": "x4_lingfeizhe_emo",
        "女2": "x4_lingxiaowan_en",
        "男2": "x4_lingfeizhe_zl",
    }
    #text=text[0]+text
    vcn_code = VOICE_MAP.get(voice_role, "x4_yezi")
    print(f"   >>> TTS开始: 角色[{voice_role}] -> 发音人[{vcn_code}]")

    ws_param = Ws_Param(
        APPID=TTS_APPID,
        APIKey=TTS_APIKey,
        APISecret=TTS_APISecret,
        Text=text,
        vcn=vcn_code,
    )
    # 3. 准备同步信号
    done_event = threading.Event()

    # --- WebSocket 回调函数定义 ---

    def on_open(ws):
        """连接建立后，立刻发送数据"""

        def run(*args):
            # 构造完整的发送数据包
            d = {
                "common": ws_param.CommonArgs,
                "business": ws_param.BusinessArgs,
                "data": ws_param.Data,
            }
            d = json.dumps(d)
            print(f"   >>> 发送文本数据...")
            ws.send(d)

        threading.Thread(target=run).start()

    def on_message(ws, message):
        try:
            message = json.loads(message)
            code = message["code"]
            status = message["data"]["status"]
            #print(message)
            if status == 2:
                print("ws is closed")
                ws.close()
            if code != 0:
                print(f"   !!! TTS API Error Code: {code}, Msg: {message['message']}")
                ws.close()
            else:
                #print("   >>> 音频接收完毕")
                audio = message["data"]["audio"]
                audio = base64.b64decode(audio)
                with open(path+"/t.mp3", "ab") as f:
                    f.write(audio)


        except Exception as e:
            print(f"   !!! TTS 解析异常: {e}")
            ws.close()
            done_event.set()

    def on_error(ws, error):
        print(f"   !!! TTS 连接错误: {error}")
        done_event.set()

    def on_close(ws, *args):
        print("   >>> TTS 连接关闭")
        done_event.set()
    websocket.enableTrace(False)
    wsUrl = ws_param.create_url()
    ws = websocket.WebSocketApp(
        wsUrl,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    t = threading.Thread(
        target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}}
    )
    t.start()

    finished = done_event.wait(timeout=60)

    if not finished:
        print("   !!! TTS 任务超时")
        ws.close()
    with open("./t.mp3", "rb") as f:
        res = f.read()
    os.remove(path + "/t.mp3")
    return res


def generate_image(
    prompt: str, model_name: str = "noobai3", width: int = 512, lenth: int = 512
):

    model_path = {
        "zimage": "redcraftRedzimageUpdatedDEC03_redzimage15AIO",
        "qwen": "qwen_masterpieces_v3",
        "noobai1": "AddMicroDetails_NoobAI_v3",
        "noobai2": "noobai_vpred_1_flat_color_v2",
        "noobai3": "noobai_vpred_1_masterpieces_v23",
        "noobai4": "SLE_v2",
        "noobai5": "MeMaXL5 Type A Vpred Wai2",
    }
    model_path = {
        a: r"D:\Downloads\models" + b + ".safetensors" for a, b in model_path.items()
    }
    model_path = model_path[model_name]
    base_model_id = "runwayml/stable-diffusion-v1-5"
    try:
        unet = UNet2DConditionModel.from_pretrained(
            base_model_id, subfolder="unet", local_files_only=False
        )
        text_encoder = CLIPTextModel.from_pretrained(
            base_model_id, subfolder="text_encoder", local_files_only=False
        )
        tokenizer = CLIPTokenizer.from_pretrained(
            base_model_id, subfolder="tokenizer", local_files_only=False
        )

        print("成功加载模型组件")

    except Exception as e:
        print(f"加载组件失败: {e}")
    vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse")

    pipe = StableDiffusionPipeline.from_single_file(
        pretrained_model_link_or_path=model_path,
        unet=unet,  # 传入已加载的UNet
        text_encoder=text_encoder,  # 传入文本编码器
        tokenizer=tokenizer,  # 传入分词器
        vae=vae,  # 关键：传入已加载的VAE模型对象
        torch_dtype=torch.float16,  # 保持精度一致
        safety_checker=None,  # 可选，避免安全检查器警告
        requires_safety_checker=False,
    )
    pipe = pipe.to("cuda")
    print("管道加载成功！")

    # 现在可以使用管道生成图像了
    image = pipe(
        prompt=prompt, num_inference_steps=20, height=lenth, width=width
    ).images[0]
    return image

def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
def _save_binary(path, data):
    _ensure_dir(os.path.dirname(path))
    with open(path, 'wb') as f:
        f.write(data)
    

