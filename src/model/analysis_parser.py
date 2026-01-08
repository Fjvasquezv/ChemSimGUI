import os
import subprocess
import numpy as np
import csv

class AnalysisParser:
    def __init__(self):
        pass

    # =========================================================================
    # SECCIÓN 1: LECTURA Y PARSEO DE ARCHIVOS DE DATOS
    # =========================================================================

    def get_data_from_file(self, filepath):
        """
        Lee archivos de resultados para graficar.
        Soporta formato .xvg (GROMACS) y .csv (TRAVIS).
        
        Args:
            filepath (str): Ruta al archivo.
            
        Returns:
            tuple: (lista_etiquetas, array_x, lista_de_arrays_y)
        """
        x_data = []
        y_data = []
        labels = ["Eje X", "Eje Y"]
        
        if not os.path.exists(filepath):
            return labels, [], []

        try:
            # --- CASO A: ARCHIVO TRAVIS (.CSV) ---
            if filepath.endswith('.csv'):
                with open(filepath, 'r') as f:
                    # Travis suele usar punto y coma ';' como delimitador
                    reader = csv.reader(f, delimiter=';')
                    
                    for row in reader:
                        if not row:
                            continue
                        
                        # Intentar detectar etiquetas en la cabecera
                        # Travis suele poner unidades como "r / pm"
                        if not row[0][0].isdigit() and not row[0].startswith('-'): 
                            if len(row) > 1 and ("r / pm" in row[0] or "Distance" in row[0]):
                                labels = [row[0], row[1]]
                            continue
                        
                        try:
                            # Columna 0: X (Distancia), Columna 1: Y (RDF)
                            val_x = float(row[0])
                            val_y = float(row[1])
                            x_data.append(val_x)
                            y_data.append(val_y)
                        except ValueError:
                            continue
                
                # Retornar en formato estándar (Y como lista de arrays)
                return labels, np.array(x_data), [np.array(y_data)]

            # --- CASO B: ARCHIVO GROMACS (.XVG) ---
            else:
                with open(filepath, 'r') as f:
                    lines = f.readlines()

                raw_data = []
                for line in lines:
                    line = line.strip()
                    
                    # Leer metadatos de los ejes (@)
                    if line.startswith("@"):
                        if "xaxis" in line and "label" in line:
                            parts = line.split('"')
                            if len(parts) > 1:
                                labels[0] = parts[1]
                        if "yaxis" in line and "label" in line:
                            parts = line.split('"')
                            if len(parts) > 1:
                                labels[1] = parts[1]
                        continue
                    
                    # Ignorar comentarios (#)
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
                
                # Convertir a matriz numpy
                data_np = np.array(raw_data)
                
                # La primera columna es X
                x_col = data_np[:, 0]
                
                # El resto de columnas son Y (puede haber temperatura, presión, etc. juntas)
                y_cols = []
                for i in range(1, data_np.shape[1]):
                    y_cols.append(data_np[:, i])
                
                return labels, x_col, y_cols

        except Exception as e:
            print(f"Error parseando archivo {filepath}: {e}")
            return labels, [], []

    # =========================================================================
    # SECCIÓN 2: EJECUCIÓN DE HERRAMIENTAS GROMACS BÁSICAS
    # =========================================================================

    def run_gmx_energy(self, edr_file, output_xvg, terms):
        """
        Ejecuta 'gmx energy' para extraer propiedades.
        """
        if not os.path.exists(edr_file):
            return False, "No existe el archivo .edr"

        # Construir input para el pipe: Lista de términos + 0 para finalizar
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
                return True, "Análisis de energía completado."
            else:
                return False, f"Error GROMACS Energy:\n{stderr}"
        except Exception as Ex:
            return False, str(Ex)

    def run_trjconv(self, tpr_file, xtc_file, output_xtc, center_group, output_group):
        """
        Ejecuta 'gmx trjconv' para corregir PBC (Periodic Boundary Conditions).
        Usa flags -pbc mol -center.
        """
        # Input interactivo: Grupo para centrar + Grupo de salida
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
                return True, "Trayectoria corregida exitosamente."
            else:
                return False, f"Error TRJCONV:\n{stderr}"
        except Exception as Ex:
            return False, str(Ex)

    # =========================================================================
    # SECCIÓN 3: GESTIÓN DE GRUPOS Y ESTRUCTURA (MAKE_NDX)
    # =========================================================================
    
    def scan_structure_atoms(self, gro_file):
        """
        Lee un archivo .gro y extrae un mapa de residuos y sus átomos.
        Usado para el explorador visual.
        Retorna: { "SOL": set("OW", "HW1", "HW2"), ... }
        """
        if not os.path.exists(gro_file):
            return {}
        
        structure_map = {}
        
        try:
            with open(gro_file, 'r') as f:
                lines = f.readlines()
                
            # Formato .gro estándar:
            # Línea 1: Título
            # Línea 2: Número de átomos
            # Líneas 3 a N-1: Datos de átomos
            # Línea N: Vectores de caja
            
            # Iteramos desde la línea 2 hasta la penúltima
            for line in lines[2:-1]:
                # Columnas fijas (Fixed Width)
                # 0-5: Residue Number
                # 5-10: Residue Name
                # 10-15: Atom Name
                
                if len(line) < 15:
                    continue
                    
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

    def get_gromacs_groups(self, tpr_file, working_dir):
        """
        Obtiene el diccionario de grupos {Nombre: ID} del archivo index.ndx.
        Si no existe, ejecuta gmx make_ndx una vez para generarlo por defecto.
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        # Si no existe, creamos el default invocando make_ndx y saliendo ('q')
        if not os.path.exists(ndx_file):
            self.add_custom_group(tpr_file, working_dir, "q")
            
        groups = {}
        if not os.path.exists(ndx_file):
            return groups
        
        current_id = 0
        try:
            with open(ndx_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # En archivos ndx, los encabezados de grupo son: [ System ]
                    if line.startswith("[") and line.endswith("]"):
                        group_name = line[1:-1].strip()
                        groups[group_name] = current_id
                        current_id += 1
            return groups
        except Exception:
            return {}

    def add_custom_group(self, tpr_file, working_dir, selection_str):
        """
        Añade un grupo personalizado al archivo index.ndx usando make_ndx.
        
        Args:
            selection_str: Comando de selección (ej: "a OW" o "r SOL")
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        cmd = ["gmx", "make_ndx", "-f", tpr_file, "-o", ndx_file]
        
        # Si ya existe un índice, lo cargamos para no perder grupos anteriores
        if os.path.exists(ndx_file):
            cmd.extend(["-n", ndx_file])
        
        # Input: Comando de selección + 'q' para guardar y salir
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
                return False, f"Error en make_ndx:\n{stderr}"
        except Exception as e:
            return False, str(e)

    # =========================================================================
    # SECCIÓN 4: EJECUCIÓN DE RDF (GROMACS Y TRAVIS)
    # =========================================================================

    def run_gmx_rdf(self, tpr_file, xtc_file, output_xvg, ref_id, sel_id, working_dir, use_com, bin_width):
        """
        Ejecuta 'gmx rdf'.
        
        Args:
            use_com (bool): Si True, usa centros de masa (-selrpos mol_com).
            bin_width (float): Ancho del bin en nm.
        """
        ndx_file = os.path.join(working_dir, "index.ndx")
        
        cmd = [
            "gmx", "rdf", 
            "-s", tpr_file, 
            "-f", xtc_file, 
            "-o", output_xvg, 
            "-n", ndx_file
        ]
        
        # Opción: Centros de Masa
        if use_com:
            cmd.extend(["-selrpos", "mol_com", "-seltype", "mol_com"])
        
        # Opción: Resolución (Bins) - Feature Solicitado
        if bin_width > 0:
            cmd.extend(["-bin", str(bin_width)])
        
        # Input: ID Referencia + ID Selección
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
                return True, "RDF GROMACS calculado exitosamente."
            else:
                return False, f"Error GROMACS RDF:\n{stderr}"
        except Exception as e:
            return False, str(e)

    def run_travis_rdf(self, struct_file, traj_file, output_csv, mol1_name, mol2_name):
        """
        Ejecuta TRAVIS para calcular RDF entre dos tipos de moléculas.
        """
        input_filename = "travis_input.txt"
        
        # Crear archivo de script para Travis
        try:
            with open(input_filename, 'w') as f:
                f.write(f"rdf molecule {mol1_name} molecule {mol2_name}\n")
        except Exception as e:
            return False, f"Error creando input Travis: {e}"
            
        cmd = ["travis", "-p", struct_file, "-i", traj_file]
        
        try:
            # Ejecutar Travis inyectando el archivo de script
            with open(input_filename, 'r') as f_in:
                process = subprocess.Popen(
                    cmd, 
                    stdin=f_in, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                stdout, stderr = process.communicate()
            
            # Limpiar archivo temporal
            if os.path.exists(input_filename):
                os.remove(input_filename)
            
            # Travis genera nombres automáticos complejos. Buscamos el output.
            expected_name = f"rdf_molecule_{mol1_name}_molecule_{mol2_name}.csv"
            
            if os.path.exists(expected_name):
                # Renombrar al archivo de salida solicitado por la App
                if os.path.exists(output_csv):
                    os.remove(output_csv)
                os.rename(expected_name, output_csv)
                return True, "RDF TRAVIS calculado exitosamente."
            else:
                return False, f"Travis finalizó pero no generó '{expected_name}'.\nLog:\n{stdout}\n{stderr}"
                
        except Exception as e:
            return False, str(e)