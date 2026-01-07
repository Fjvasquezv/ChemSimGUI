import os
import json
from datetime import datetime

class ProjectManager:
    def __init__(self):
        self.current_project_path = None
        self.project_data = {}

    def create_project(self, name, root_path):
        """Crea estructura física"""
        self.current_project_path = os.path.join(root_path, name)
        try:
            dirs = ["storage", "templates", "logs", "analysis"]
            for f in dirs:
                os.makedirs(os.path.join(self.current_project_path, f), exist_ok=True)
            
            # Datos base
            self.project_data = {
                "name": name,
                "created_at": str(datetime.now()),
                "last_modified": str(datetime.now()),
                # Aquí guardaremos el estado de las pestañas
                "setup_state": {},
                "topology_state": {},
                "simulation_state": []
            }
            self.save_db()
            return True, f"Proyecto creado en {self.current_project_path}"
        except Exception as e:
            return False, str(e)

    def load_project_from_path(self, full_path):
        """Carga un proyecto existente leyendo su JSON"""
        db_path = os.path.join(full_path, "project_db.json")
        if not os.path.exists(db_path):
            return False, "No se encontró project_db.json en la carpeta."
        
        try:
            self.current_project_path = full_path
            with open(db_path, 'r') as f:
                self.project_data = json.load(f)
            return True, "Proyecto cargado."
        except Exception as e:
            return False, f"Error leyendo JSON: {e}"

    def save_db(self):
        """Escribe el estado actual en disco"""
        if self.current_project_path:
            self.project_data["last_modified"] = str(datetime.now())
            db_path = os.path.join(self.current_project_path, "project_db.json")
            with open(db_path, 'w') as f:
                json.dump(self.project_data, f, indent=4)

    # Métodos para guardar partes específicas del estado
    def update_tab_state(self, tab_name, data):
        self.project_data[f"{tab_name}_state"] = data
        self.save_db()

    def get_tab_state(self, tab_name):
        return self.project_data.get(f"{tab_name}_state", {})