import math
import os
import re

class ChemistryTools:
    def __init__(self):
        self.ATOMIC_MASSES = {
            "H": 1.008, "HE": 4.0026, "LI": 6.94, "BE": 9.0122,
            "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999,
            "F": 18.998, "NE": 20.180, "NA": 22.990, "MG": 24.305,
            "AL": 26.982, "SI": 28.085, "P": 30.974, "S": 32.06,
            "CL": 35.45, "K": 39.098, "AR": 39.948, "CA": 40.078,
            "FE": 55.845, "ZN": 65.38, "BR": 79.904, "I": 126.90
        }

    # ... (Métodos get_mw_from_pdb, calculate_box_size... IGUALES QUE ANTES) ...
    # Pongo aquí los métodos anteriores resumidos para no perderlos
    def get_mw_from_pdb(self, pdb_path):
        total_mw = 0.0
        try:
            with open(pdb_path, 'r') as f:
                for line in f:
                    if line.startswith("ATOM") or line.startswith("HETATM"):
                        element = line[76:78].strip().upper()
                        if not element:
                            atom_name = line[12:16].strip().upper()
                            element = atom_name[0]
                            if len(atom_name) > 1 and atom_name[1].isalpha():
                                potential = atom_name[0:2]
                                if potential in self.ATOMIC_MASSES: element = potential
                        total_mw += self.ATOMIC_MASSES.get(element, 0.0)
            return round(total_mw, 3)
        except: return 0.0

    def calculate_box_size_mixing_rule(self, molecules, margin_percent=0.0):
        avogadro = 6.022e23
        total_vol_A3 = 0.0
        for mol in molecules:
            mw = float(mol['mw']); count = int(mol['count']); rho = float(mol['density_kg_m3'])
            if rho <= 0: continue
            mass_g = (mw * count) / avogadro
            vol_cm3 = mass_g / (rho / 1000.0)
            total_vol_A3 += vol_cm3 * 1e24
        return round(math.pow(total_vol_A3, 1/3) * (1.0 + margin_percent/100.0), 2)

    def generate_packmol_input(self, inp_path, out_pdb, box, molecules, tol=2.0):
        try:
            os.makedirs(os.path.dirname(inp_path), exist_ok=True)
            with open(inp_path, 'w') as f:
                f.write(f"tolerance {tol}\nfiletype pdb\noutput {out_pdb}\n\n")
                for mol in molecules:
                    f.write(f"structure {mol['pdb']}\n  number {mol['count']}\n  inside cube 0. 0. 0. {box}\nend structure\n\n")
            return True, "OK"
        except Exception as e: return False, str(e)

    # --- NUEVA LÓGICA DE PROCESAMIENTO DE ITP ---

    def sanitize_itps(self, storage_dir, itp_files):
        """
        1. Lee ITPs.
        2. Extrae [ atomtypes ] y los renombra para evitar colisiones.
        3. Genera ITPs limpios modificando SOLO la columna de 'type' en [ atoms ],
           dejando el 'atom name' intacto para que coincida con el GRO/PDB.
        """
        master_atomtypes = []
        new_itp_filenames = []
        
        try:
            for itp_file in itp_files:
                filename = os.path.basename(itp_file)
                # Prefijo limpio (ej: CO2_TRAPPE_)
                clean_name = os.path.splitext(filename)[0].replace(".", "").replace(" ", "").upper()
                prefix = f"{clean_name}_"
                
                path = os.path.join(storage_dir, filename)
                with open(path, 'r') as f:
                    lines = f.readlines()
                
                clean_lines = []
                current_section = None
                atomtypes_map = {} # Viejo -> Nuevo
                
                # --- PASO A: Extraer Atomtypes y Crear Mapa ---
                # Primero una pasada para identificar tipos y crear el mapa
                for line in lines:
                    strip_line = line.strip()
                    if strip_line.startswith('[') and strip_line.endswith(']'):
                        current_section = strip_line[1:-1].strip()
                        continue
                    
                    if current_section == 'atomtypes' and strip_line and not strip_line.startswith(';'):
                        parts = strip_line.split()
                        if len(parts) >= 1:
                            old_type = parts[0]
                            new_type = prefix + old_type
                            atomtypes_map[old_type] = new_type
                            
                            # Preparar línea para el maestro
                            parts[0] = new_type
                            master_atomtypes.append(f"{' '.join(parts)} ; from {filename}\n")

                # --- PASO B: Reescribir el Archivo (Quirúrgico) ---
                current_section = None
                
                for line in lines:
                    strip_line = line.strip()
                    
                    # Detectar cambio de sección
                    if strip_line.startswith('[') and strip_line.endswith(']'):
                        current_section = strip_line[1:-1].strip()
                        
                        # Si es atomtypes, la omitimos (ya la movimos al maestro)
                        if current_section == 'atomtypes':
                            clean_lines.append(f"; [ atomtypes ] moved to merged_atomtypes.itp\n")
                            continue # Saltamos al siguiente loop, no escribimos el header [atomtypes]
                        
                        # Escribimos el header de otras secciones ([ atoms ], [ bonds ]...)
                        clean_lines.append(line)
                        continue
                    
                    # Si estamos dentro de [ atomtypes ], ignoramos el contenido
                    if current_section == 'atomtypes':
                        continue

                    # SI ESTAMOS EN [ atoms ]: AQUÍ ESTÁ EL FIX
                    if current_section == 'atoms' and strip_line and not strip_line.startswith(';'):
                        parts = line.split() # Split por espacios
                        # Estructura típica: nr type resnr residue atom cgnr charge mass
                        # Indices (0-based): 0  1    2     3       4    5    6      7
                        
                        if len(parts) >= 5:
                            old_type = parts[1]
                            
                            # Si el tipo está en nuestro mapa, lo reemplazamos
                            if old_type in atomtypes_map:
                                parts[1] = atomtypes_map[old_type]
                            
                            # IMPORTANTE: parts[4] (atom name) SE QUEDA INTACTO.
                            # Reconstruimos la línea manteniendo formato tabular simple
                            clean_lines.append("\t".join(parts) + "\n")
                        else:
                            clean_lines.append(line)
                    
                    else:
                        # Cualquier otra sección ([ bonds ], comentarios, etc) se copia tal cual.
                        # NOTA: Si los [ bonds ] usaran tipos explícitos en lugar de índices, 
                        # habría que mapearlos también, pero lo estándar es índices.
                        clean_lines.append(line)

                # Guardar archivo limpio
                new_filename = f"clean_{filename}"
                new_path = os.path.join(storage_dir, new_filename)
                with open(new_path, 'w') as f:
                    f.write(f"; Pre-processed by ChemSimGUI (Prefix: {prefix})\n")
                    f.write("".join(clean_lines))
                
                new_itp_filenames.append(new_filename)

            # --- PASO C: Escribir Maestro ---
            merged_path = os.path.join(storage_dir, "merged_atomtypes.itp")
            with open(merged_path, 'w') as f:
                f.write("[ atomtypes ]\n")
                f.write("; name  at.num  mass  charge  ptype  sigma  epsilon\n")
                f.writelines(master_atomtypes)

            return True, new_itp_filenames

        except Exception as e:
            return False, f"Error en sanitización: {str(e)}"

    def generate_topology_file(self, top_path, global_includes, molecule_itps, molecules_list, forcefield="oplsaa.ff", include_water=True):
        """Genera topol.top (Versión Final)"""
        try:
            with open(top_path, 'w') as f:
                f.write(f"; Generado por ChemSimGUI\n\n")
                
                # 1. Include Forcefield
                if not forcefield.endswith(".itp"):
                    f.write(f'#include "{forcefield}/forcefield.itp"\n\n')
                else:
                    f.write(f'#include "{forcefield}"\n\n')
                
                # 2. Includes Globales (Atomtypes, ions, merged types)
                # Aquí inyectamos el merged_atomtypes.itp si existe en la lista
                if global_includes:
                    f.write(f'; Global parameters (Atomtypes)\n')
                    for inc in global_includes:
                        f.write(f'#include "{os.path.basename(inc)}"\n')
                    f.write(f'\n')

                # 3. Molecule Topologies
                if molecule_itps:
                    f.write(f'; Molecule topologies\n')
                    for itp in molecule_itps:
                        f.write(f'#include "{os.path.basename(itp)}"\n')
                    f.write(f'\n')
                
                # 4. Standard Water/Ions
                if include_water:
                    f.write(f'; Water and Ions\n')
                    f.write(f'#include "{forcefield}/spce.itp"\n')
                    f.write(f'#include "{forcefield}/ions.itp"\n\n')

                # 5. System
                f.write(f'[ system ]\n; Name\nSimulacion_ChemSimGUI\n\n')
                
                # 6. Composition
                f.write(f'[ molecules ]\n; Compound    #mols\n')
                for mol in molecules_list:
                    name = mol.get('mol_name', 'MOL') 
                    count = mol.get('count', 0)
                    f.write(f'{name:<15} {count}\n')
            
            return True, f"OK"
        except Exception as e: return False, str(e)

    def get_moleculetype_name_from_itp(self, itp_path):
        """
        Lee un archivo ITP y busca el nombre definido en [ moleculetype ].
        Retorna el nombre (str) o None si no lo encuentra.
        """
        try:
            with open(itp_path, 'r') as f:
                lines = f.readlines()
            
            in_moltype = False
            for line in lines:
                # Quitar comentarios y espacios
                clean_line = line.split(';')[0].strip()
                if not clean_line: continue
                
                # Detectar sección
                if clean_line.startswith('[') and 'moleculetype' in clean_line:
                    in_moltype = True
                    continue
                
                if in_moltype:
                    # La primera línea válida después de [ moleculetype ] es el nombre
                    # Formato: Nombre  nrexcl
                    parts = clean_line.split()
                    if len(parts) >= 1:
                        return parts[0] # Retorna el nombre real (ej: CO2N o CO2_CLEAN)
            
            return None
        except Exception:
            return None