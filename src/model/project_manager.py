import os
import json
from datetime import datetime

class ProjectManager:
    def __init__(self):
        self.current_project_path = None
        self.project_data = {}

    def create_project(self, name, root_path):
        """Crea la estructura física y lógica del proyecto"""
        self.current_project_path = os.path.join(root_path, name)
        
        # 1. Crear directorios físicos
        try:
            folders = ["storage", "templates", "logs", "analysis"]
            for f in folders:
                os.makedirs(os.path.join(self.current_project_path, f), exist_ok=True)
            
            # 2. Crear base de datos lógica
            self.project_data = {
                "name": name,
                "created_at": str(datetime.now()),
                "description": "Tesis Maestría Ingeniería Química",
                "simulations": []
            }
            self.save_db()
            return True, f"Proyecto '{name}' creado en {root_path}"
        except Exception as e:
            return False, str(e)

    def save_db(self):
        if self.current_project_path:
            path = os.path.join(self.current_project_path, "project_db.json")
            with open(path, 'w') as f:
                json.dump(self.project_data, f, indent=4)