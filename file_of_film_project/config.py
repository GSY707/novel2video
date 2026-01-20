import os

ROOT_DIR = "C:\web\project_files"

def _get_project_dir(project_name):
    return os.path.join(ROOT_DIR, project_name)