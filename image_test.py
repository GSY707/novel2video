from image_api import generate_image, get_model_list

# 1. 打印模型列表
#print(get_model_list())
#print(get_model_list().keys)
# 2. 生成测试
for i in get_model_list().keys():
    if 'Z Image' in i: continue
    img_data = generate_image("1girl, anime style, smile", model_name=i)

# 3. 保存看结果
    with open(i+"test_output.png", "wb") as f:
        f.write(img_data)


