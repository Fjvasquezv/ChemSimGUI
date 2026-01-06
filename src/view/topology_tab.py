import os
import shutil
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QGroupBox, QFormLayout, QFileDialog, QMessageBox, 
                             QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QListWidget, QHBoxLayout, QCheckBox)
from src.model.chemistry_tools import ChemistryTools
from src.controller.workers import CommandWorker

class TopologyTab(QWidget):
    def __init__(self):
        super().__init__()
        self.chem_tools = ChemistryTools()
        self.project_mgr = None 
        self.current_project_path = None
        self.molecules_data = [] 
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- 1. Conversión ---
        group_conv = QGroupBox("1. Estructura")
        l_conv = QVBoxLayout()
        self.btn_convert_gro = QPushButton("Convertir PDB -> GRO")
        self.btn_convert_gro.clicked.connect(self.run_editconf)
        self.btn_convert_gro.setEnabled(False)
        l_conv.addWidget(self.btn_convert_gro)
        group_conv.setLayout(l_conv)
        layout.addWidget(group_conv)
        
        # --- 2. Topología ---
        group_top = QGroupBox("2. Constructor de Topología")
        l_top = QVBoxLayout()
        
        # Forcefield
        self.combo_ff = QComboBox()
        self.combo_ff.addItems(["oplsaa.ff", "amber99sb.ff", "charmm36.ff", "gromos54a7.ff"])
        l_top.addWidget(QLabel("Forcefield:"))
        l_top.addWidget(self.combo_ff)
        
        # OPCIÓN DE SANITIZACIÓN (LA CLAVE)
        self.chk_sanitize = QCheckBox("🛠️ Auto-corregir ITPs (Extraer [atomtypes] y renombrar para evitar colisiones)")
        self.chk_sanitize.setChecked(True)
        self.chk_sanitize.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.chk_sanitize.setToolTip("Separa los atomtypes en un archivo maestro y renombra átomos duplicados.")
        l_top.addWidget(self.chk_sanitize)
        
        # Includes Globales
        l_top.addWidget(QLabel("Includes Globales Manuales (ej: atomtypes extra):"))
        self.list_globals = QListWidget()
        self.list_globals.setMaximumHeight(60)
        l_top.addWidget(self.list_globals)
        
        h_glob = QHBoxLayout()
        b_add_g = QPushButton("Cargar .itp Global"); b_add_g.clicked.connect(self.add_global_include)
        b_del_g = QPushButton("Borrar"); b_del_g.clicked.connect(self.remove_global_include)
        h_glob.addWidget(b_add_g); h_glob.addWidget(b_del_g)
        l_top.addLayout(h_glob)

        # Tabla Moléculas
        l_top.addWidget(QLabel("Moléculas:"))
        self.table_mols = QTableWidget()
        self.table_mols.setColumnCount(3)
        self.table_mols.setHorizontalHeaderLabels(["Input", "Nombre Topología", "Archivo .itp"])
        self.table_mols.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l_top.addWidget(self.table_mols)
        
        self.chk_water = QCheckBox("Incluir Agua Estándar (spce/ions)")
        self.chk_water.setChecked(False) # Por defecto false para tu caso
        l_top.addWidget(self.chk_water)

        self.btn_gen = QPushButton("Generar topol.top")
        self.btn_gen.clicked.connect(self.generate_topology)
        self.btn_gen.setEnabled(False)
        self.btn_gen.setStyleSheet("color: green; font-weight: bold;")
        l_top.addWidget(self.btn_gen)
        
        group_top.setLayout(l_top)
        layout.addWidget(group_top)
        self.setLayout(layout)

    # ... (MÉTODOS update_project_data, refresh_table, run_editconf IGUALES) ...
    # Copialos del código anterior o usa este bloque resumido:

    def update_project_data(self, project_mgr, mols):
        self.project_mgr = project_mgr
        self.current_project_path = project_mgr.current_project_path
        self.molecules_data = mols
        self.btn_convert_gro.setEnabled(True)
        self.btn_gen.setEnabled(True)
        self.refresh_table()

    def refresh_table(self):
        self.table_mols.setRowCount(len(self.molecules_data))
        for i, mol in enumerate(self.molecules_data):
            self.table_mols.setItem(i, 0, QTableWidgetItem(mol['pdb']))
            guess = os.path.splitext(mol['pdb'])[0][:4].upper()
            self.table_mols.setItem(i, 1, QTableWidgetItem(guess))
            
            btn = QPushButton("Cargar .itp")
            btn.clicked.connect(lambda ch, r=i: self.select_itp_mol(r))
            self.table_mols.setCellWidget(i, 2, btn)

    def select_itp_mol(self, row):
        f, _ = QFileDialog.getOpenFileName(self, "ITP", "", "*.itp")
        if f:
            self.copy_to_storage(f)
            self.table_mols.removeCellWidget(row, 2)
            self.table_mols.setItem(row, 2, QTableWidgetItem(os.path.basename(f)))

    def add_global_include(self):
        fs, _ = QFileDialog.getOpenFileNames(self, "ITP", "", "*.itp")
        if fs:
            for f in fs:
                self.copy_to_storage(f)
                self.list_globals.addItem(os.path.basename(f))

    def remove_global_include(self):
        self.list_globals.takeItem(self.list_globals.currentRow())

    def copy_to_storage(self, f):
        d = os.path.join(self.current_project_path, "storage")
        try: shutil.copy(f, os.path.join(d, os.path.basename(f)))
        except: pass

    def run_editconf(self):
        d = os.path.join(self.current_project_path, "storage")
        cmd = ["gmx", "editconf", "-f", "system_init.pdb", "-o", "system.gro"]
        self.worker = CommandWorker(cmd, d)
        self.worker.finished_signal.connect(lambda s, m: QMessageBox.information(self, "Info", m) if s else QMessageBox.warning(self, "Error", m))
        self.worker.start()

    # --- LÓGICA DE GENERACIÓN MEJORADA ---

    def generate_topology(self):
        storage_dir = os.path.join(self.current_project_path, "storage")
        top_file = os.path.join(storage_dir, "topol.top")
        
        # 1. Recoger datos crudos de la GUI
        raw_mol_itps = [] 
        final_mols_list = []
        
        # Mapa: índice de fila -> nombre de archivo ITP original
        row_to_itp_map = {}

        for i in range(self.table_mols.rowCount()):
            gmx_name_gui = self.table_mols.item(i, 1).text() # Nombre que puso el usuario (ej CO2)
            count = self.molecules_data[i]['count']
            
            # Chequear si tiene ITP asignado
            itp_item = self.table_mols.item(i, 2)
            itp_filename = None
            
            if itp_item and itp_item.text():
                itp_filename = itp_item.text()
                raw_mol_itps.append(itp_filename)
                row_to_itp_map[i] = itp_filename
            
            # Guardamos temporalmente el nombre de la GUI
            final_mols_list.append({'mol_name': gmx_name_gui, 'count': count, 'has_itp': bool(itp_filename)})
        
        global_incs = [self.list_globals.item(i).text() for i in range(self.list_globals.count())]

        # 2. PROCESAMIENTO INTELIGENTE (SANITIZACIÓN)
        final_itps_to_include = []
        
        # Mapa: Nombre original -> Nombre final (puede ser 'clean_xxx.itp')
        itp_name_mapping = {} 

        if self.chk_sanitize.isChecked() and raw_mol_itps:
            success, result = self.chem_tools.sanitize_itps(storage_dir, raw_mol_itps)
            
            if success:
                clean_itps = result 
                if "merged_atomtypes.itp" not in global_incs:
                    global_incs.insert(0, "merged_atomtypes.itp")
                
                # Crear mapeo de ITP original a limpio
                # Asumimos que el orden se mantiene en sanitize_itps
                for idx, original in enumerate(raw_mol_itps):
                    itp_name_mapping[original] = clean_itps[idx]
                    
                final_itps_to_include = clean_itps
                
                QMessageBox.information(self, "Sanitización", "ITPs corregidos y merged_atomtypes.itp generado.")
            else:
                QMessageBox.warning(self, "Error Sanitización", f"{result}\nUsando originales.")
                final_itps_to_include = raw_mol_itps
                for orig in raw_mol_itps: itp_name_mapping[orig] = orig
        else:
            final_itps_to_include = raw_mol_itps
            for orig in raw_mol_itps: itp_name_mapping[orig] = orig

        # 3. AUTO-CORRECCIÓN DE NOMBRES DE MOLÉCULA
        # Aquí solucionamos el error: Leemos el nombre real dentro del ITP que se va a usar
        for i, mol_data in enumerate(final_mols_list):
            if mol_data['has_itp']:
                # 1. ¿Cuál fue el ITP original asignado a esta fila?
                original_itp = row_to_itp_map.get(i)
                # 2. ¿Cuál es el ITP final (limpio u original) que se usará?
                final_itp_name = itp_name_mapping.get(original_itp)
                
                if final_itp_name:
                    full_path = os.path.join(storage_dir, final_itp_name)
                    # 3. Leer el nombre real dentro del archivo
                    real_name = self.chem_tools.get_moleculetype_name_from_itp(full_path)
                    
                    if real_name:
                        # SOBRESCRIBIR EL NOMBRE. Esto arregla el "No such moleculetype"
                        mol_data['mol_name'] = real_name
                        print(f"DEBUG: Corrigiendo nombre molécula {i}: GUI={mol_data['mol_name']} -> REAL={real_name}")

        # 4. GENERAR TOPOL.TOP
        # Nota: pasamos una lista de ITPs únicos para los includes
        unique_itps = sorted(list(set(final_itps_to_include)))
        
        success, msg = self.chem_tools.generate_topology_file(
            top_file,
            global_includes=global_incs,
            molecule_itps=unique_itps, 
            molecules_list=final_mols_list,
            forcefield=self.combo_ff.currentText(),
            include_water=self.chk_water.isChecked()
        )
        
        if success:
            QMessageBox.information(self, "Éxito", f"Topología generada.\nNombres sincronizados con ITPs.")
        else:
            QMessageBox.critical(self, "Error", msg)