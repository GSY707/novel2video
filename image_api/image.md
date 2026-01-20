image_api模块设计
实现目标：
提供接口：

根据提示词生成一张图片
这个调用应该是简单得，由模块处理所有复杂的事情
generate_image(prompt,model_name=default_name,width=1024,lenth=1024)
return 二进制图片文件

查看有哪些可以使用的模型
get_model_list()
{
    模型名称：模型描述（包含模型速度，模型作者的表述，模型特色，模型对使用者的要求）
}

查看这个模型有哪些lora可用
get_lora_list(model_name)
{
    lora名称：lora描述（包含lora类型，lora作者的对Lora的表述，模型特色，模型对使用者的要求）
}

实现要求：尽可能降低调用者的能力要求，在这个模块中做出充分的兼容性设计

部署要求：
模型文件单独存放并下载。如果需要将这个模块转移至其他电脑，应该保证只移动模型文件夹和这个模块文件夹，再通过网络下载少于100MB的文件后即可运行。

具体实现：
文件结构
/image_api/config.py#存储所有配置
/image_api/core.py#核心代码
/image_api/__init__.py
/image_api/其他文件
/image_api/model/这个文件夹下存放所有模型文件，建议建立子文件夹分类保存

需要部署以下模型：
Z Image Turbo，Qwen-Image，Z Image Turbo FP8，NoobAI-XL，MiaoMiao Harem，KOALA-1B