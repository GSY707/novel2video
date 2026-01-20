from openai import OpenAI
import os
import json
import base64
import hashlib
import hmac
import ssl
import threading
from datetime import datetime
from time import mktime
from urllib.parse import urlencode
from wsgiref.handlers import format_date_time
from openai import OpenAI
import websocket
import torch
from diffusers import StableDiffusionPipeline, AutoencoderKL, UNet2DConditionModel
from transformers import CLIPTextModel, CLIPTokenizer
import os

API_KEY = "sk-l1KAedCgobQEP1pp7f8a4eA9Fa5a4e649500Fe92B7258c9a"
API_BASE = "http://maas-api.cn-huabei-1.xf-yun.com/v1"
TTS_APPID = "d19f2d7f"
TTS_APISecret = "NTdhODY2MDI4YjRhZTU0NGVjNzBhYTBh"
TTS_APIKey = "13484d7d67ad29d3bdc7da2c6e32c1ec"


def llm(prompt: str, llm_name: str) -> str:

    client = OpenAI(api_key=API_KEY, base_url=API_BASE)
    match llm_name:
        case "DeepSeek":
            model_id = "xopdeepseekv32"
        case "Qwen":
            model_id = "xop3qwen1b7"
        case _:
            pass
    messages = [{"role": "user", "content": prompt}]
    try:
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=False,
            temperature=0.7,
            max_tokens=4096,
            extra_headers={
                "lora_id": "0"
            },  # 调用微调大模型时,对应替换为模型服务卡片上的resourceId
            stream_options={"include_usage": True},
        )
        message = response.choices[0].message
        return message.content
    except Exception as e:
        print(f"{e}")


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


def tts(text: str, voice_role: str = "narrator"):
    VOICE_MAP = {
        "narrator": "x4_yezi",  # 旁白/解说
        "young_man": "aisjiuxu",  # 年轻男性
        "young_woman": "aisjinger",  # 年轻女性
        "old_woamn": "x4_xiaoyan",  # 老年女性
        "cute_boy": "aisbabyxu",  # 小男孩
    }
    # 1. 映射 voice_role 到 讯飞 vcn
    # 如果字典里没有，默认使用 x4_yezi
    vcn_code = VOICE_MAP.get(voice_role, "x4_yezi")
    print(f"   >>> TTS开始: 角色[{voice_role}] -> 发音人[{vcn_code}]")

    # 2. 初始化参数对象
    ws_param = Ws_Param(
        APPID=TTS_APPID,
        APIKey=TTS_APIKey,
        APISecret=TTS_APISecret,
        Text=text,
        vcn=vcn_code,
    )
    res = None
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

            if code != 0:
                print(f"   !!! TTS API Error Code: {code}, Msg: {message['message']}")
                ws.close()
                done_event.set()
            else:
                data = message["data"]["audio"]
                audio = base64.b64decode(data)

                if message["data"]["status"] == 2:
                    print("   >>> 音频接收完毕")
                    ws.close()
                    done_event.set()
                    nonlocal res
                    res = audio
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

    # --- 启动 WebSocket ---
    # 禁止 websocket 库的调试输出干扰视线
    websocket.enableTrace(False)

    wsUrl = ws_param.create_url()
    ws = websocket.WebSocketApp(
        wsUrl,
        on_open=on_open,  # <--- 关键修复：必须挂载 on_open
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    t = threading.Thread(
        target=ws.run_forever, kwargs={"sslopt": {"cert_reqs": ssl.CERT_NONE}}
    )
    t.start()

    # 等待任务完成，最多等待 60 秒
    finished = done_event.wait(timeout=60)

    if not finished:
        print("   !!! TTS 任务超时")
        ws.close()
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
    checkpoint_path = r"D:\Downloads\models\noobai_vpred_1_masterpieces_v23.safetensors"

    pipe = StableDiffusionPipeline.from_single_file(
        pretrained_model_link_or_path=checkpoint_path,
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


if __name__ == "__main__":
    t = generate_image("a nude girl")
    t.show()
