from image_api import generate_image, get_model_list

# 1. 打印模型列表
#print(get_model_list())
#print(get_model_list().keys)
# 2. 生成测试
prompt='''masterpiece, best quality, 8k, highly detailed, extreme close-up, a handwritten
  note, text reads: ''If you are not too tired tomorrow... I would like to invite
  you: to eat instant noodles together at midnight?'', the note is in the center of
  the frame, text is clearly visible, slightly blurred background, cinematic lighting,
  soft focus, shallow depth of field, paper texture, handwritten, emotional, sincere
  invitation'''
img_data = generate_image("1girl, anime style, smile", model_name="NoobAI-XL", width=832, height=1216)

# 3. 保存看结果
with open("NoobAI"+"test_output.png", "wb") as f:
    f.write(img_data)


