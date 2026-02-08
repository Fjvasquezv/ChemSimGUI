import os
import shutil
import json
import copy
import re
from datetime import datetime

class ProjectManager:
    def __init__(self):
        self.current_project_path = None
        self.active_system_name = None 
        self.project_data = {}
        
        # Gestión de Configuración Global (Recientes)
        # Se guardará en la carpeta config/ o en la raíz
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(self.root_dir, "config", "global_config.json")
        self.recent_projects = []
        
        self.load_global_config()

    # =========================================================================
    # GESTIÓN DE CONFIGURACIÓN GLOBAL (RECIENTES)
    # =========================================================================
    
    def load_global_config(self):
        """Carga la lista de proyectos recientes desde el JSON global"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self.recent_projects = data.get("recent_projects", [])
            except Exception:
                self.recent_projects = []
        else:
            self.recent_projects = []

    def save_global_config(self):
        """Guarda la configuración global"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "recent_projects": self.recent_projects
        }
        try:
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error guardando config global: {e}")

    def add_to_recent(self, path):
        """Añade un proyecto a la lista de recientes (Max 5)"""
        # Normalizar ruta
        path = os.path.normpath(path)
        
        # Eliminar si ya existe para moverlo al principio
        if path in self.recent_projects:
            self.recent_projects.remove(path)
            
        # Insertar al inicio
        self.recent_projects.insert(0, path)
        
        # Mantener solo los últimos 5
        if len(self.recent_projects) > 5:
            self.recent_projects = self.recent_projects[:5]
            
        self.save_global_config()

    def get_recent_projects(self):
        return self.recent_projects

    # =========================================================================
    # GESTIÓN DEL PROYECTO ACTUAL
    # =========================================================================

    def create_project(self, name, root_path):
        self.current_project_path = os.path.join(root_path, name)
        try:
            os.makedirs(os.path.join(self.current_project_path, "storage"), exist_ok=True)
            os.makedirs(os.path.join(self.current_project_path, "analysis"), exist_ok=True)
            
            self.project_data = {
                "name": name,
                "created_at": str(datetime.now()),
                "systems": {}, 
                "active_system": None,
                "global_states": {} 
            }
            
            self.create_system("Default_System")
            
            self.save_db()
            
            # AGREGAR A RECIENTES
            self.add_to_recent(self.current_project_path)
            
            return True, f"Proyecto creado en {self.current_project_path}"
        except Exception as e:
            return False, str(e)

    def load_project_from_path(self, full_path):
        db_path = os.path.join(full_path, "project_db.json")
        if not os.path.exists(db_path):
            return False, "No es un proyecto válido (falta project_db.json)."
        
        try:
            self.current_project_path = full_path
            with open(db_path, 'r') as f:
                self.project_data = json.load(f)
            
            active = self.project_data.get("active_system")
            systems = list(self.project_data.get("systems", {}).keys())
            
            if active and active in systems:
                self.active_system_name = active
            elif systems:
                self.active_system_name = systems[0]
            else:
                self.create_system("Default_System")
            
            # AGREGAR A RECIENTES
            self.add_to_recent(self.current_project_path)
                
            return True, "Proyecto cargado."
        except Exception as e:
            return False, f"Error JSON: {e}"

    def save_db(self):
        if self.current_project_path:
            self.project_data["active_system"] = self.active_system_name
            
            # Guardado atómico para evitar corrupción
            db_path = os.path.join(self.current_project_path, "project_db.json")
            tmp_path = db_path + ".tmp"
            
            try:
                with open(tmp_path, 'w') as f:
                    json.dump(self.project_data, f, indent=4)
                    
                # Si se escribió bien, reemplazamos el original
                # En Windows rename no es atómico si existe, pero aquí estamos en Linux
                if os.path.exists(db_path):
                    os.replace(tmp_path, db_path)
                else:
                    os.rename(tmp_path, db_path)
            except Exception as e:
                print(f"Error guardando DB: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

    # --- GESTIÓN DE SISTEMAS ---

    def create_system(self, sys_name):
        if sys_name in self.project_data.get("systems", {}):
            return False, "Ya existe."
        
        sys_path = os.path.join(self.current_project_path, "storage", sys_name)
        os.makedirs(sys_path, exist_ok=True)
        
        if "systems" not in self.project_data: self.project_data["systems"] = {}
        
        self.project_data["systems"][sys_name] = {
            "created": str(datetime.now()),
            "setup_state": {},
            "topology_state": {},
            "simulation_state": {},
            "analysis_state": {}
        }
        
        self.active_system_name = sys_name
        self.save_db()
        return True, sys_path

    def clone_system(self, new_name, source_name):
        if new_name in self.project_data["systems"]:
            return False, "Nombre existe."
        if source_name not in self.project_data["systems"]:
            return False, "Origen no existe."

        source_data = self.project_data["systems"][source_name]
        new_data = copy.deepcopy(source_data)
        new_data["created"] = str(datetime.now())
        
        # Resetear estados de simulación
        sim_state = new_data.get("simulation_state", {})
        if "tree_data" in sim_state:
            self._reset_tree_status(sim_state["tree_data"])
            
        self.project_data["systems"][new_name] = new_data
        
        src_path = os.path.join(self.current_project_path, "storage", source_name)
        dst_path = os.path.join(self.current_project_path, "storage", new_name)
        os.makedirs(dst_path, exist_ok=True)
        
        allowed = ['.mdp', '.itp', '.top', '.pdb'] 
        
        try:
            for item in os.listdir(src_path):
                if any(item.endswith(ext) for ext in allowed):
                    s = os.path.join(src_path, item)
                    d = os.path.join(dst_path, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)
        except Exception as e:
            return False, f"Error copiando: {e}"

        self.active_system_name = new_name
        self.save_db()
        return True, "Clonado."

    def _reset_tree_status(self, nodes):
        for node in nodes:
            node['status'] = "Pendiente"
            if 'children' in node:
                self._reset_tree_status(node['children'])

    def delete_system(self, sys_name):
        if sys_name not in self.project_data.get("systems", {}):
            return False, "No existe."
            
        sys_path = os.path.join(self.current_project_path, "storage", sys_name)
        try:
            if os.path.exists(sys_path):
                shutil.rmtree(sys_path)
        except Exception as e:
            return False, str(e)
            
        del self.project_data["systems"][sys_name]
        
        if self.active_system_name == sys_name:
            keys = list(self.project_data["systems"].keys())
            if keys:
                self.active_system_name = keys[0]
            else:
                self.active_system_name = None
                self.create_system("Default_System")
        
        self.save_db()
        return True, "Eliminado."

    def get_active_system_path(self):
        if not self.current_project_path or not self.active_system_name: return None
        return os.path.join(self.current_project_path, "storage", self.active_system_name)

    def update_tab_state(self, tab, data):
        if self.active_system_name:
            self.project_data["systems"][self.active_system_name][f"{tab}_state"] = data
            self.save_db()

    def get_tab_state(self, tab):
        if self.active_system_name:
            return self.project_data["systems"][self.active_system_name].get(f"{tab}_state", {})
        return {}

    def update_global_state(self, key, data):
        if "global_states" not in self.project_data:
            self.project_data["global_states"] = {}
        self.project_data["global_states"][key] = data
        self.save_db()

    def get_global_state(self, key):
        return self.project_data.get("global_states", {}).get(key, {})
    
    def get_system_list(self):
        return list(self.project_data.get("systems", {}).keys())

    # =========================================================================
    # RECONSTRUCCIÓN DE ÁRBOL (para recuperación de corrupción)
    # =========================================================================

    def rebuild_tree_from_storage(self, system_name=None):
        """
        Reconstruye el árbol de simulaciones (simulation_state.tree_data) escaneando
        el directorio storage. Útil cuando el JSON se corrompe o los nodos se pierden.
        
        Args:
            system_name: Si se especifica, solo reconstruye ese sistema. Si no, reconstruye todos.
        
        Returns:
            Tupla (éxito: bool, mensaje: str)
        """
        if system_name:
            systems_to_rebuild = [system_name]
        else:
            systems_to_rebuild = list(self.project_data.get("systems", {}).keys())
        
        VALID_SIM_PATTERN = re.compile(
            r'^(minim|gen(?:\d+\.\d+)?|equil(?:\d+\.\d+)?|prod(?:\d+\.\d+(?:_rdf_batch_\d+_\d+)?)?)$'
        )
        
        def is_valid_sim_name(name):
            # Excluir cualquier nombre que contenga _prev
            if '_prev' in name:
                return False
            return bool(VALID_SIM_PATTERN.match(name))
        
        def extract_temp(name):
            match = re.search(r'(\d{3,4})', name)
            if match:
                return int(match.group(1))
            if name in ('gen', 'equil', 'prod'):
                return 253
            return None
        
        def build_tree(storage_path):
            """Construye el árbol para un sistema desde su directorio storage."""
            nodes_by_name = {}
            nodes_list = []
            
            if not os.path.isdir(storage_path):
                return nodes_list
            
            seen_bases = set()
            for fname in os.listdir(storage_path):
                base = fname
                for ext in ['.cpt', '.edr', '.gro', '.log', '.mdp', '.tpr', '.xtc', '.xvg']:
                    if fname.endswith(ext):
                        base = fname[:-len(ext)]
                        break
                
                if not is_valid_sim_name(base) or base in seen_bases:
                    continue
                seen_bases.add(base)
                
                temp = extract_temp(base)
                node_type = 'minim'
                if base.startswith('gen'):
                    node_type = 'gen'
                elif base.startswith('equil'):
                    node_type = 'nvt'
                elif base.startswith('prod'):
                    node_type = 'prod'
                
                node = {
                    'name': base,
                    'type': node_type,
                    'status': 'Completado',
                    'children': [],
                    'temperature': temp
                }
                
                nodes_by_name[base] = node
                if node_type == 'minim':
                    nodes_list.append(node)
            
            # Construir jerarquía: minim -> gen -> equil -> prod
            minim_node = None
            for name, node in nodes_by_name.items():
                if node['type'] == 'minim':
                    minim_node = node
                    break
            
            if not minim_node:
                return nodes_list
            
            # Adjuntar gen nodes a minim
            gen_nodes = {n: nd for n, nd in nodes_by_name.items() if nd['type'] == 'gen'}
            for gen_name in sorted(gen_nodes.keys()):
                gen_node = gen_nodes[gen_name]
                minim_node['children'].append(gen_node)
                
                # Adjuntar equil nodes a gen (matching temperature)
                gen_temp = gen_node.get('temperature')
                equil_nodes = {n: nd for n, nd in nodes_by_name.items()
                              if nd['type'] == 'nvt' and nd.get('temperature') == gen_temp}
                for equil_name in sorted(equil_nodes.keys()):
                    equil_node = equil_nodes[equil_name]
                    if equil_node not in gen_node['children']:
                        gen_node['children'].append(equil_node)
                        
                        # Adjuntar prod nodes a equil (matching temperature)
                        equil_temp = equil_node.get('temperature')
                        prod_nodes = {n: nd for n, nd in nodes_by_name.items()
                                    if nd['type'] == 'prod' and nd.get('temperature') == equil_temp}
                        for prod_name in sorted(prod_nodes.keys()):
                            prod_node = prod_nodes[prod_name]
                            if prod_node not in equil_node['children']:
                                equil_node['children'].append(prod_node)
            
            return nodes_list
        
        # Reconstruir árboles
        try:
            summary = {}
            for sys_name in systems_to_rebuild:
                if sys_name not in self.project_data.get("systems", {}):
                    continue
                
                sys_data = self.project_data["systems"][sys_name]
                storage_path = os.path.join(self.current_project_path, "storage", sys_name)
                
                old_tree = sys_data.get("simulation_state", {}).get("tree_data", [])
                new_tree = build_tree(storage_path)
                
                old_count = sum(1 + len(n.get('children', [])) for n in old_tree)
                new_count = sum(1 + len(n.get('children', [])) for n in new_tree)
                
                summary[sys_name] = {"old": old_count, "new": new_count}
                
                # Actualizar árbol
                if "simulation_state" not in sys_data:
                    sys_data["simulation_state"] = {}
                sys_data["simulation_state"]["tree_data"] = new_tree
            
            # Guardar cambios
            self.save_db()
            
            # Mensaje de resumen
            msg = "Árboles reconstruidos:\n"
            for sys, counts in summary.items():
                msg += f"  {sys}: {counts['old']} → {counts['new']} nodos\n"
            
            return True, msg.strip()
        
        except Exception as e:
            return False, f"Error reconstruyendo árbol: {e}"