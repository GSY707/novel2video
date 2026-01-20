project_name="story"
from modules.processor import *
from multiprocessing import freeze_support
from modules.video_generator import generate_video
#delete_project_folder(project_name)
#create_project_folder(project_name)

analyze_text_to_shots(project_name)


generate_all(project_name)


generate_video(
        project_name,
        force=False,
        resume=True
    )
