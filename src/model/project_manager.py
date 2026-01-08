import os
import shutil
import json
from datetime import datetime

class ProjectManager:
    def __init__(self):
        self.current_project_path = None
        self.active_system_name = None # Nombre del sistema actual (ej: "10_CBD")
        self.project_data = {}

    def create_project(self, name, root_path):
        """Crea el contenedor principal del proyecto"""
        self.current_project_path = os.path.join(root_path, name)
        try:
            # Carpetas globales
            os.makedirs(os.path.join(self.current_project_path, "storage"), exist_ok=True)
            
            self.project_data = {
                "name": name,
                "created_at": str(datetime.now()),
                "systems": {}, # Diccionario de sistemas { "Nombre": {estados...} }
                "active_system": None
            }
            
            # Crear un sistema por defecto
            self.create_system("Default_System")
            
            self.save_db()
            return True, f"Proyecto creado en {self.current_project_path}"
        except Exception as e:
            return False, str(e)

    def load_project_from_path(self, full_path):
        """Carga proyecto y establece el sistema activo"""
        db_path = os.path.join(full_path, "project_db.json")
        if not os.path.exists(db_path):
            return False, "No es un proyecto válido."
        
        try:
            self.current_project_path = full_path
            with open(db_path, 'r') as f:
                self.project_data = json.load(f)
            
            # Recuperar último sistema activo o el primero
            active = self.project_data.get("active_system")
            systems = list(self.project_data.get("systems", {}).keys())
            
            if active and active in systems:
                self.active_system_name = active
            elif systems:
                self.active_system_name = systems[0]
            else:
                self.create_system("Default_System")
                
            return True, "Proyecto cargado."
        except Exception as e:
            return False, f"Error JSON: {e}"

    def save_db(self):
        if self.current_project_path:
            self.project_data["active_system"] = self.active_system_name
            db_path = os.path.join(self.current_project_path, "project_db.json")
            with open(db_path, 'w') as f:
                json.dump(self.project_data, f, indent=4)

    # --- GESTIÓN DE SISTEMAS ---

    def create_system(self, sys_name):
        """Crea un nuevo sistema vacío"""
        if sys_name in self.project_data.get("systems", {}):
            return False, "Ya existe un sistema con ese nombre."
        
        # Crear carpeta física
        sys_path = os.path.join(self.current_project_path, "storage", sys_name)
        os.makedirs(sys_path, exist_ok=True)
        
        # Inicializar datos en JSON
        if "systems" not in self.project_data: self.project_data["systems"] = {}
        
        self.project_data["systems"][sys_name] = {
            "created": str(datetime.now()),
            "setup_state": {},
            "topology_state": {},
            "simulation_state": {}
        }
        
        self.active_system_name = sys_name
        self.save_db()
        return True, sys_path

    def clone_system(self, new_name, source_name):
        """
        Clona la CONFIGURACIÓN de un sistema a otro nuevo.
        NO clona los archivos generados (traj, tpr, gro) para evitar corrupción.
        SÍ clona los archivos de entrada esenciales (itps, mdps).
        """
        if new_name in self.project_data["systems"]:
            return False, "El nombre destino ya existe."
        
        if source_name not in self.project_data["systems"]:
            return False, "El sistema origen no existe."

        # 1. Crear entrada en JSON copiando los estados
        source_data = self.project_data["systems"][source_name]
        # Usamos deepcopy conceptual (json dump/load es una forma fácil de clonar dicts)
        import copy
        new_data = copy.deepcopy(source_data)
        new_data["created"] = str(datetime.now())
        self.project_data["systems"][new_name] = new_data
        
        # 2. Crear carpetas físicas
        src_path = os.path.join(self.current_project_path, "storage", source_name)
        dst_path = os.path.join(self.current_project_path, "storage", new_name)
        os.makedirs(dst_path, exist_ok=True)
        
        # 3. Copiar archivos ESENCIALES (MDPs, ITPs, PDBs base)
        # NO copiamos .tpr, .xtc, .log, .edr
        valid_extensions = ['.mdp', '.itp', '.pdb', '.top'] 
        
        try:
            for item in os.listdir(src_path):
                if any(item.endswith(ext) for ext in valid_extensions):
                    s = os.path.join(src_path, item)
                    d = os.path.join(dst_path, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)
        except Exception as e:
            return False, f"Error copiando archivos: {e}"

        self.active_system_name = new_name
        self.save_db()
        return True, "Sistema clonado exitosamente."

    def get_active_system_path(self):
        """Retorna la ruta física del sistema actual"""
        if not self.current_project_path or not self.active_system_name: return None
        return os.path.join(self.current_project_path, "storage", self.active_system_name)

    # --- ESTADO DE PESTAÑAS (Ahora relativo al sistema) ---

    def update_tab_state(self, tab_name, data):
        if self.active_system_name:
            self.project_data["systems"][self.active_system_name][f"{tab_name}_state"] = data
            self.save_db()

    def get_tab_state(self, tab_name):
        if self.active_system_name:
            return self.project_data["systems"][self.active_system_name].get(f"{tab_name}_state", {})
        return {}
    
    def get_system_list(self):
        return list(self.project_data.get("systems", {}).keys())