import os
import math
import graphviz

class MoleculeGraphGenerator:
    def __init__(self):
        # Radios covalentes aproximados (Angstroms) para heurística de enlaces
        self.COVALENT_RADII = {
            'H': 0.31, 'C': 0.76, 'N': 0.71, 'O': 0.66, 
            'P': 1.07, 'S': 1.05, 'F': 0.57, 'CL': 1.02, 
            'BR': 1.20, 'I': 1.39
        }
        # Colores para el grafo
        self.COLORS = {
            'C': '#909090', 'O': 'red', 'N': 'blue', 'H': 'white', 
            'S': 'yellow', 'P': 'orange', 'F': 'green', 'CL': 'green'
        }

    def get_element_from_name(self, atom_name):
        """Intenta deducir el elemento (C, O, N...) del nombre (CA, OW, H1)"""
        # Quitar números y espacios
        clean = ''.join([i for i in atom_name if not i.isdigit()]).strip().upper()
        if not clean: return 'C'
        
        # Casos de 2 letras (CL, BR, FE)
        if len(clean) >= 2 and clean[:2] in self.COVALENT_RADII:
            return clean[:2]
        # Casos de 1 letra
        return clean[0]

    def parse_residue_structure(self, gro_file, target_res_name):
        """
        Lee el GRO y extrae átomos y coordenadas de la PRIMERA ocurrencia del residuo.
        Retorna: lista de dicts [{'name': 'C1', 'x': 1.0, 'y': 2.0, 'z': 3.0, 'elem': 'C'}, ...]
        """
        atoms = []
        found_residue = False
        target_res_id = None

        with open(gro_file, 'r') as f:
            lines = f.readlines()

        # Omitir cabecera (2 líneas) y caja (última)
        for line in lines[2:-1]:
            try:
                # GRO Fixed format
                # Residue Number (0-5)
                res_num = line[0:5].strip()
                res_name = line[5:10].strip()
                atom_name = line[10:15].strip()
                # Coordenadas (nm)
                x = float(line[20:28]) * 10.0 # Convertir a Angstroms
                y = float(line[28:36]) * 10.0
                z = float(line[36:44]) * 10.0
                
                if res_name == target_res_name:
                    if target_res_id is None:
                        target_res_id = res_num # Fijar el ID de la primera molécula encontrada
                    
                    if res_num == target_res_id:
                        atoms.append({
                            'name': atom_name,
                            'x': x, 'y': y, 'z': z,
                            'elem': self.get_element_from_name(atom_name)
                        })
                        found_residue = True
                    else:
                        # Si ya cambiamos de número de residuo, terminamos (solo queremos 1 molécula)
                        break
                elif found_residue:
                    break # Ya pasamos el bloque
            except ValueError:
                continue
                
        return atoms

    def generate_image(self, gro_file, res_name, output_path):
        """
        Genera una imagen PNG de la estructura usando Graphviz.
        """
        atoms = self.parse_residue_structure(gro_file, res_name)
        if not atoms:
            return False, "No se encontró el residuo en el archivo GRO."

        # Configurar Graphviz (Motor 'neato' es mejor para estructuras químicas)
        dot = graphviz.Graph(comment=res_name, format='png', engine='neato')
        dot.attr(bgcolor='white', overlap='false', splines='true', sep='0.2')
        dot.attr('node', shape='circle', style='filled', fontname='Arial', fontsize='10', fixedsize='true', width='0.6')
        
        # 1. Crear Nodos
        for i, atom in enumerate(atoms):
            elem = atom['elem']
            color = self.COLORS.get(elem, 'lightgrey')
            font_color = 'white' if elem in ['O', 'N', 'CL', 'F'] else 'black'
            
            # Etiqueta: Nombre real del átomo (ej. OW, CA)
            label = atom['name']
            
            dot.node(str(i), label=label, fillcolor=color, fontcolor=font_color)

        # 2. Calcular Enlaces (Heurística de Distancia)
        # O(N^2) pero N es pequeño (<100 átomos por molécula usualmente)
        for i in range(len(atoms)):
            for j in range(i + 1, len(atoms)):
                a1 = atoms[i]
                a2 = atoms[j]
                
                # Distancia Euclídea
                dist = math.sqrt((a1['x']-a2['x'])**2 + (a1['y']-a2['y'])**2 + (a1['z']-a2['z'])**2)
                
                # Umbral de enlace: Suma de radios + 20% tolerancia
                r1 = self.COVALENT_RADII.get(a1['elem'], 1.5)
                r2 = self.COVALENT_RADII.get(a2['elem'], 1.5)
                threshold = (r1 + r2) * 1.3 
                
                # Filtro mínimo para no unir hidrógenos entre sí (0.5A)
                if 0.5 < dist < threshold:
                    # Añadir arista (enlace)
                    # len=dist le dice a neato que respete la distancia proporcional
                    dot.edge(str(i), str(j), len=str(dist*0.8), penwidth='2', color='#404040')

        try:
            # Renderizar
            # output_path debe ser sin extensión, graphviz añade .png
            base_out = os.path.splitext(output_path)[0]
            dot.render(base_out, cleanup=True)
            return True, f"{base_out}.png"
        except Exception as e:
            return False, f"Error Graphviz: {e}\n¿Está instalado? (sudo apt install graphviz)"