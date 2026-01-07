import os
import shutil
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QGroupBox, QFormLayout, QFileDialog, QMessageBox, 
                             QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
                             QListWidget, QHBoxLayout, QCheckBox)
from PyQt6.QtCore import Qt
from src.model.chemistry_tools import ChemistryTools
from src.controller.workers import CommandWorker

class TopologyTab(QWidget):
    def __init__(self):
        super().__init__()
        self.chem_tools = ChemistryTools()
        self.project_mgr = None 
        self.current_project_path = None
        self.molecules_data = [] 
        self.global_includes = []
        self.box_size_nm = 0.0
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- SECCIÓN 1: Estado de Estructura (Automático) ---
        group_struc = QGroupBox("1. Estructura (system.gro)")
        l_struc = QVBoxLayout()
        
        # En lugar de un botón, usamos una etiqueta informativa
        self.lbl_gro_status = QLabel("Estado: Esperando datos...")
        self.lbl_gro_status.setStyleSheet("color: gray; font-style: italic;")
        self.lbl_gro_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        l_struc.addWidget(self.lbl_gro_status)
        group_struc.setLayout(l_struc)
        layout.addWidget(group_struc)
        
        # --- SECCIÓN 2: Topología ---
        group_top = QGroupBox("2. Constructor de Topología (topol.top)")
        l_top = QVBoxLayout()
        
        # Forcefield
        self.combo_ff = QComboBox()
        self.combo_ff.addItems(["oplsaa.ff", "amber99sb.ff", "charmm36.ff", "gromos54a7.ff"])
        l_top.addWidget(QLabel("Forcefield:"))
        l_top.addWidget(self.combo_ff)
        
        # Sanitización
        self.chk_sanitize = QCheckBox("🛠️ Auto-corregir ITPs (Extraer [atomtypes] y evitar colisiones)")
        self.chk_sanitize.setChecked(True)
        l_top.addWidget(self.chk_sanitize)
        
        # Includes Globales
        l_top.addWidget(QLabel("Includes Globales Manuales:"))
        self.list_globals = QListWidget()
        self.list_globals.setMaximumHeight(60)
        l_top.addWidget(self.list_globals)
        
        h_glob = QHBoxLayout()
        b_add_g = QPushButton("Cargar Global"); b_add_g.clicked.connect(self.add_global_include)
        b_del_g = QPushButton("Borrar"); b_del_g.clicked.connect(self.remove_global_include)
        h_glob.addWidget(b_add_g); h_glob.addWidget(b_del_g)
        l_top.addLayout(h_glob)

        # Tabla Moléculas
        l_top.addWidget(QLabel("Asignación de ITPs por Molécula:"))
        self.table_mols = QTableWidget()
        self.table_mols.setColumnCount(3)
        self.table_mols.setHorizontalHeaderLabels(["PDB Input", "Nombre Topología", "Archivo .itp"])
        self.table_mols.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        l_top.addWidget(self.table_mols)
        
        self.chk_water = QCheckBox("Incluir Agua Estándar (spce/ions)")
        self.chk_water.setChecked(False) 
        l_top.addWidget(self.chk_water)

        self.btn_gen = QPushButton("Generar topol.top")
        self.btn_gen.clicked.connect(self.generate_topology)
        self.btn_gen.setEnabled(False)
        self.btn_gen.setStyleSheet("color: green; font-weight: bold;")
        l_top.addWidget(self.btn_gen)
        
        group_top.setLayout(l_top)
        layout.addWidget(group_top)
        self.setLayout(layout)

    # --- LÓGICA AUTOMÁTICA ---

    def update_project_data(self, project_mgr, molecules, box_size_angstrom=0.0):
        """
        Se llama automáticamente cuando el usuario entra a esta pestaña.
        Aquí disparamos la conversión automática.
        """
        self.project_mgr = project_mgr
        self.current_project_path = project_mgr.current_project_path
        self.molecules_data = molecules
        self.box_size_nm = box_size_angstrom / 10.0
        
        self.btn_gen.setEnabled(True)
        self.refresh_table()

        # DISPARO AUTOMÁTICO DE EDITCONF
        self.run_editconf_auto()

    def run_editconf_auto(self):
        """Ejecuta editconf en segundo plano sin molestar al usuario"""
        storage_dir = os.path.join(self.current_project_path, "storage")
        pdb_file = os.path.join(storage_dir, "system_init.pdb")
        
        if not os.path.exists(pdb_file):
            self.lbl_gro_status.setText("⚠️ Alerta: No se encontró system_init.pdb (Ejecute Packmol primero)")
            self.lbl_gro_status.setStyleSheet("color: orange; font-weight: bold;")
            return
            
        if self.box_size_nm <= 0:
            self.lbl_gro_status.setText("⚠️ Alerta: Tamaño de caja es 0 (Configure en Pestaña 2)")
            return

        # Actualizar UI para mostrar que estamos trabajando
        self.lbl_gro_status.setText("⏳ Generando system.gro con dimensiones actualizadas...")
        self.lbl_gro_status.setStyleSheet("color: blue;")

        val = str(self.box_size_nm)
        cmd = ["gmx", "editconf", "-f", "system_init.pdb", "-o", "system.gro", "-box", val, val, val]
        
        self.worker = CommandWorker(cmd, storage_dir)
        # No usamos popups, solo actualizamos la etiqueta al terminar
        self.worker.finished_signal.connect(self.on_editconf_finished)
        self.worker.start()

    def on_editconf_finished(self, success, msg):
        if success:
            self.lbl_gro_status.setText(f"✅ system.gro generado exitosamente (Caja: {self.box_size_nm} nm)")
            self.lbl_gro_status.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.lbl_gro_status.setText("❌ Error generando system.gro (Ver logs)")
            self.lbl_gro_status.setStyleSheet("color: red; font-weight: bold;")
            # Solo mostramos popup si falla, porque es crítico
            QMessageBox.warning(self, "Error GROMACS", f"Falló editconf:\n{msg}")

    # --- RESTO DE LÓGICA (Topología) ---

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

    def generate_topology(self):
        storage_dir = os.path.join(self.current_project_path, "storage")
        top_file = os.path.join(storage_dir, "topol.top")
        
        raw_mol_itps = [] 
        final_mols_list = []
        row_to_itp_map = {}

        for i in range(self.table_mols.rowCount()):
            gmx_name = self.table_mols.item(i, 1).text()
            itp_item = self.table_mols.item(i, 2)
            itp_filename = None
            if itp_item and itp_item.text():
                itp_filename = itp_item.text()
                raw_mol_itps.append(itp_filename)
                row_to_itp_map[i] = itp_filename
            
            final_mols_list.append({'mol_name': gmx_name, 'count': self.molecules_data[i]['count'], 'has_itp': bool(itp_filename)})
        
        global_incs = [self.list_globals.item(i).text() for i in range(self.list_globals.count())]

        # Sanitización
        final_itps_to_include = raw_mol_itps
        itp_name_mapping = {orig: orig for orig in raw_mol_itps}

        if self.chk_sanitize.isChecked() and raw_mol_itps:
            success, result = self.chem_tools.sanitize_itps(storage_dir, raw_mol_itps)
            if success:
                clean_itps = result 
                if "merged_atomtypes.itp" not in global_incs:
                    global_incs.insert(0, "merged_atomtypes.itp")
                
                for idx, original in enumerate(raw_mol_itps):
                    itp_name_mapping[original] = clean_itps[idx]
                final_itps_to_include = clean_itps
                QMessageBox.information(self, "Sanitización", "ITPs corregidos automáticamente.")
            else:
                QMessageBox.warning(self, "Aviso", f"Sanitización falló: {result}\nUsando originales.")

        # Auto-corrección de nombres
        for i, mol_data in enumerate(final_mols_list):
            if mol_data['has_itp']:
                orig = row_to_itp_map.get(i)
                final = itp_name_mapping.get(orig)
                if final:
                    real = self.chem_tools.get_moleculetype_name_from_itp(os.path.join(storage_dir, final))
                    if real: mol_data['mol_name'] = real

        # Generar
        unique_itps = sorted(list(set(final_itps_to_include)))
        success, msg = self.chem_tools.generate_topology_file(
            top_file, global_incs, unique_itps, final_mols_list,
            self.combo_ff.currentText(), self.chk_water.isChecked()
        )
        
        if success: QMessageBox.information(self, "Éxito", "Topología generada.")
        else: QMessageBox.critical(self, "Error", msg)
    
    def get_state(self):
        # Guardar mapeo de ITPs de la tabla
        itp_mapping = {}
        for i in range(self.table_mols.rowCount()):
            pdb_name = self.table_mols.item(i, 0).text()
            itp_item = self.table_mols.item(i, 2)
            if itp_item and itp_item.text():
                itp_mapping[pdb_name] = itp_item.text()

        # Guardar globals
        globals_list = [self.list_globals.item(i).text() for i in range(self.list_globals.count())]

        return {
            "forcefield": self.combo_ff.currentIndex(),
            "sanitize": self.chk_sanitize.isChecked(),
            "include_water": self.chk_water.isChecked(),
            "global_includes": globals_list,
            "itp_mapping": itp_mapping
        }

    def set_state(self, state):
        if not state: return
        
        self.combo_ff.setCurrentIndex(state.get("forcefield", 0))
        self.chk_sanitize.setChecked(state.get("sanitize", True))
        self.chk_water.setChecked(state.get("include_water", False))
        
        # Restaurar lista globales
        self.list_globals.clear()
        for g in state.get("global_includes", []):
            self.list_globals.addItem(g)
            
        # Nota: La tabla de moléculas se reconstruye sola cuando cambias de pestaña
        # usando update_project_data, así que solo necesitamos guardar el mapeo de ITPs
        # para restaurarlo cuando se llene la tabla. (Ver siguiente cambio)
        self.saved_itp_mapping = state.get("itp_mapping", {})

    # MODIFICAR refresh_table PARA USAR EL MAPEO GUARDADO
    def refresh_table(self):
        self.table_mols.setRowCount(len(self.molecules_data))
        # Intentar recuperar mapeo guardado si existe
        mapping = getattr(self, 'saved_itp_mapping', {})
        
        for i, mol in enumerate(self.molecules_data):
            pdb = mol['pdb']
            self.table_mols.setItem(i, 0, QTableWidgetItem(pdb))
            guess = os.path.splitext(pdb)[0][:4].upper()
            self.table_mols.setItem(i, 1, QTableWidgetItem(guess))
            
            # Restaurar ITP si ya lo habíamos asignado antes
            prev_itp = mapping.get(pdb)
            if prev_itp:
                self.table_mols.setItem(i, 2, QTableWidgetItem(prev_itp))
            else:
                btn = QPushButton("Cargar .itp")
                btn.clicked.connect(lambda ch, r=i: self.select_itp_mol(r))
                self.table_mols.setCellWidget(i, 2, btn)
    
    