import os
import subprocess
import numpy as np
import csv

class AnalysisParser:
    def __init__(self):
        pass

    # ==========================================================
    # LECTURA DE ARCHIVOS DE DATOS (GRAFICACIÓN)
    # ==========================================================
    
    def get_data_from_file(self, filepath):
        """
        Lee archivos de datos para graficar.
        Soporta:
        1. .xvg (GROMACS)
        2. .csv (TRAVIS)
        
        Retorna: (labels_list, x_array, y_list_of_arrays)
        """
        x_data = []
        y_data = []
        labels = ["Eje X", "Eje Y"]
        
        if not os.path.exists(filepath):
            return labels, [], []

        try:
            # --- CASO 1: ARCHIVO CSV (TRAVIS) ---
            if filepath.endswith('.csv'):
                with open(filepath, 'r') as f:
                    # Travis usa punto y coma como delimitador comúnmente
                    reader = csv.reader(f, delimiter=';')
                    for row in reader:
                        if not row:
                            continue
                        
                        # Saltar headers de texto
                        if not row[0][0].isdigit() and not row[0][0] == '-': 
                            # Intentar leer etiquetas del header
                            if len(row) > 1 and "r / pm" in row[0]:
                                labels = [row[0], row[1]]
                            continue
                        
                        try:
                            # Travis: Col 0 = Distancia, Col 1 = g(r)
                            val_x = float(row[0])
                            val_y = float(row[1])
                            x_data.append(val_x)
                            y_data.append(val_y)
                        except ValueError:
                            pass
                
                # Retornar formato estándar
                return labels, np.array(x_data), [np.array(y_data)]

            # --- CASO 2: ARCHIVO XVG (GROMACS) ---
            else:
                with open(filepath, 'r') as f:
                    lines = f.readlines()

                raw_data = []
                for line in lines:
                    line = line.strip()
                    
                    # Leer metadatos de ejes
                    if line.startswith("@"):
                        if "xaxis" in line and "label" in line:
                            labels[0] = line.split('"')[1]
                        if "yaxis" in line and "label" in line:
                            labels[1] = line.split('"')[1]
                        continue
                    
                    # Ignorar comentarios
                    if line.startswith("#"):
                        continue
                    
                    # Leer datos numéricos
                    try:
                        parts = line.split()
                        nums = [float(p) for p in parts]
                        raw_data.append(nums)
                    except ValueError:
                        pass

                if not raw_data:
                    return labels, [], []
                
                # Convertir a numpy para separar columnas fácilmente
                data_np = np.array(raw_data)
                
                # Columna 0 es X
                x_col = data_np[:, 0]
                
                # Resto de columnas son Y (puede haber varias energías)
                y_cols = []
                for i in range(1, data_np.shape[1]):
                    y_cols.append(data_np[:, i])
                
                return labels, x_col, y_cols

        except Exception as e:
            print(f"Error parseando archivo {filepath}: {e}")
            return labels, [], []

    # ==========================================================
    # HERRAMIENTAS GROMACS (ENERGÍA Y PBC)
    # ==========================================================

    def run_gmx_energy(self, edr_file, output_xvg, terms):
        """
        Ejecuta gmx energy para extraer temperatura, presión, etc.
        """
        if not os.path.exists(edr_file):
            return False, "No existe el archivo .edr"

        # Construir input para el pipe: Terminos + 0 (fin)
        input_str = "\n".join(terms) + "\n0\n"
        
        cmd = ["gmx", "energy", "-f", edr_file, "-o", output_xvg]
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            stdout, stderr = process.communicate(input=input_str)
            
            if process.returncode == 0:
                return True, "Análisis completado."
            else:
                return False, f"Error GROMACS:\n{stderr}"
        except Exception as Ex:
            return False, str(Ex)

    def run_trjconv(self, tpr_file, xtc_file, output_xtc, center_group, output_group):
        """
        Corrige PBC centrando un grupo.
        """
        # Input para gmx: Grupo Centrar + Grupo Salida
        input_str = f"{center_group}\n{output_group}\n"
        
        cmd = [
            "gmx", "trjconv", 
            "-s", tpr_file, 
            "-f", xtc_file, 
            "-o", output_xtc, 
            "-pbc", "mol", 
            "-center"
        ]
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            stdout, stderr = process.communicate(input=input_str)
            
            if process.returncode == 0:
                return True, "Trayectoria corregida."
            else:
                return False, f"Error TRJCONV:\n{stderr}"
        except Exception as Ex:
            return False, str(Ex)

    # ==========================================================
    # GESTIÓN DE GRUPOS Y ESTRUCTURA (EXPLORADOR)
    # ==========================================================
    
    def scan_structure_atoms(self, gro_file):
        """
        Lee el archivo .gro para saber qué átomos existen.
        Retorna: { "NombreResiduo": set("Atomo1", "Atomo2", ...) }
        """
        if not os.path.exists(gro_file):
            return {}
        
        structure_map = {}
        
        try:
            with open(gro_file, 'r') as f:
                lines = f.readlines()
                
            # Formato .gro:
            # Linea 1: Titulo
            # Linea 2: Num atomos
            # Lineas 3 a N-1: Atomos
            # Linea N: Caja
            
            for line in lines[2:-1]:
                # Columnas fijas
                # 0-5: ResNum, 5-10: ResName, 10-15: AtomName
                res_name = line[5:10].strip()
                atom_name = line[10:15].strip()
                
                if not res_name or not atom_name:
                    continue
                
                if res_name not in structure_map:
                    structure_map[res_name] = set()
                
                structure_map[res_name].add(atom_name)
                
            return structure_map
        except Exception as e:
            print(f"Error escaneando GRO: {e}")
            return {}

    def add_custom_group(self, tpr_file, working_dir, selection_str):
        """
        Usa make_ndx para crear un grupo personalizado.
        selection_str: ej "a OW"
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        cmd = ["gmx", "make_ndx", "-f", tpr_file, "-o", ndx_file]
        
        # Si ya existe index, lo leemos para añadir, no sobrescribir
        if os.path.exists(ndx_file):
            cmd.extend(["-n", ndx_file])
        
        # Comandos: selección + q (quit)
        input_str = f"{selection_str}\nq\n"
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            stdout, stderr = process.communicate(input=input_str)
            
            if process.returncode == 0:
                return True, "Grupo agregado exitosamente."
            else:
                return False, f"Error make_ndx:\n{stderr}"
        except Exception as e:
            return False, str(e)

    def get_gromacs_groups(self, tpr_file, working_dir):
        """
        Obtiene el diccionario de grupos {Nombre: ID} del archivo index.ndx.
        Si no existe, corre make_ndx una vez para generarlo por defecto.
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        # Si no existe, creamos el default
        if not os.path.exists(ndx_file):
            # Ejecutamos con "q" para que solo guarde los defaults
            self.add_custom_group(tpr_file, working_dir, "q")
            
        groups = {}
        if not os.path.exists(ndx_file):
            return groups
        
        current_id = 0
        try:
            with open(ndx_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Los grupos se marcan como [ Nombre ]
                    if line.startswith("[") and line.endswith("]"):
                        group_name = line[1:-1].strip()
                        groups[group_name] = current_id
                        current_id += 1
            return groups
        except Exception:
            return {}

    # ==========================================================
    # EJECUCIÓN RDF (GROMACS Y TRAVIS)
    # ==========================================================

    def run_gmx_rdf(self, tpr_file, xtc_file, output_xvg, ref_id, sel_id, working_dir, use_com):
        """
        Ejecuta gmx rdf.
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        cmd = [
            "gmx", "rdf", 
            "-s", tpr_file, 
            "-f", xtc_file, 
            "-o", output_xvg, 
            "-n", ndx_file
        ]
        
        # Opción Centros de Masa
        if use_com:
            cmd.extend(["-selrpos", "mol_com", "-seltype", "mol_com"])
        
        # Input: IDs de grupos
        input_str = f"{ref_id}\n{sel_id}\n"
        
        try:
            process = subprocess.Popen(
                cmd, 
                stdin=subprocess.PIPE, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            stdout, stderr = process.communicate(input=input_str)
            
            if process.returncode == 0:
                return True, "RDF GROMACS calculado."
            else:
                return False, f"Error RDF:\n{stderr}"
        except Exception as e:
            return False, str(e)

    def run_travis_rdf(self, struct_file, traj_file, output_csv, mol1_name, mol2_name):
        """
        Ejecuta Travis para RDF.
        """
        input_filename = "travis_input.txt"
        
        # Crear script temporal para Travis
        with open(input_filename, 'w') as f:
            f.write(f"rdf molecule {mol1_name} molecule {mol2_name}\n")
            
        cmd = ["travis", "-p", struct_file, "-i", traj_file]
        
        try:
            with open(input_filename, 'r') as f_in:
                process = subprocess.Popen(
                    cmd, 
                    stdin=f_in, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                stdout, stderr = process.communicate()
            
            # Limpieza
            if os.path.exists(input_filename):
                os.remove(input_filename)
            
            # Buscar el archivo de salida (Travis tiene nombres automáticos complejos)
            expected_name = f"rdf_molecule_{mol1_name}_molecule_{mol2_name}.csv"
            
            if os.path.exists(expected_name):
                # Renombrar al output deseado
                if os.path.exists(output_csv):
                    os.remove(output_csv)
                os.rename(expected_name, output_csv)
                return True, "RDF TRAVIS calculado."
            else:
                # Si falla, devolver log para debug
                return False, f"Travis no generó el archivo esperado.\nLog:\n{stdout}\n{stderr}"
                
        except Exception as e:
            return False, str(e)