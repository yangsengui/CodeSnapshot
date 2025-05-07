import os

class ConfigOptions:
    def __init__(self) -> None:
        self.task_prefix: str = "codesnap@task/"
        self.config_dir: str = os.path.join(os.getcwd(), ".codesnap")
        self.tasks_file: str = os.path.join(self.config_dir, "tasks.json")
