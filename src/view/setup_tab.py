import os
import shutil
import subprocess  # <--- Necesario para lanzar VMD
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                             QLineEdit, QFormLayout, QGroupBox, QFileDialog, 
                             QMessageBox, QHBoxLayout, QSpinBox, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QDoubleSpinBox, QCheckBox)
from src.model.chemistry_tools import ChemistryTools
from src.controller.workers import CommandWorker

class SetupTab(QWidget):
    def __init__(self):
        super().__init__()
        self.chem_tools = ChemistryTools()
        self.current_project_path = None
        self.worker = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- SECCIÓN 1: Composición ---
        group_mol = QGroupBox("1. Composición del Sistema (Propiedades Individuales)")
        layout_mol = QVBoxLayout()
        
        self.table_comps = QTableWidget()
        self.table_comps.setColumnCount(5) # PDB, MW, Count, Density, Path
        self.table_comps.setHorizontalHeaderLabels(["Archivo PDB", "MW", "Cant.", "Densidad", "Ruta"])
        self.table_comps.setColumnHidden(4, True)
        self.table_comps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout_mol.addWidget(self.table_comps)
        
        hbox_btns = QHBoxLayout()
        self.btn_add = QPushButton("➕ Agregar")
        self.btn_add.clicked.connect(self.add_component)
        self.btn_remove = QPushButton("➖ Quitar")
        self.btn_remove.clicked.connect(self.remove_component)
        hbox_btns.addWidget(self.btn_add)
        hbox_btns.addWidget(self.btn_remove)
        layout_mol.addLayout(hbox_btns)
        
        group_mol.setLayout(layout_mol)
        layout.addWidget(group_mol)
        
        # --- SECCIÓN 2: Caja ---
        group_box = QGroupBox("2. Dimensiones de la Caja")
        form_box = QFormLayout()
        
        self.input_margin = QSpinBox()
        self.input_margin.setRange(0, 200) 
        self.input_margin.setValue(10)     
        self.input_margin.setSuffix(" % (Margen)")
        
        self.spin_box_size = QDoubleSpinBox()
        self.spin_box_size.setRange(0.0, 10000.0) 
        self.spin_box_size.setDecimals(3)         
        self.spin_box_size.setSuffix(" Å")
        self.spin_box_size.setReadOnly(True)      
        self.spin_box_size.setStyleSheet("font-weight: bold; color: blue;")
        
        self.chk_manual = QCheckBox("Modo Manual")
        self.chk_manual.toggled.connect(self.toggle_manual_mode)

        self.btn_calc = QPushButton("Calcular (Regla de Mezcla)")
        self.btn_calc.clicked.connect(self.calculate_box)
        
        form_box.addRow(self.input_margin)
        form_box.addRow(self.btn_calc)
        form_box.addRow(self.chk_manual)
        form_box.addRow("Lado de Caja:", self.spin_box_size)
        group_box.setLayout(form_box)
        layout.addWidget(group_box)
        
        # --- BOTONES DE ACCIÓN ---
        self.btn_gen_input = QPushButton("Generar packmol.inp")
        self.btn_gen_input.clicked.connect(self.generate_input_file)
        self.btn_gen_input.setEnabled(False)
        
        hbox_run = QHBoxLayout()
        self.btn_run_packmol = QPushButton("▶ Ejecutar Packmol")
        self.btn_run_packmol.clicked.connect(self.run_packmol_process)
        self.btn_run_packmol.setEnabled(False)
        self.btn_run_packmol.setStyleSheet("background-color: #d1e7dd; color: black; font-weight: bold;")
        
        self.btn_stop_packmol = QPushButton("⏹ Detener")
        self.btn_stop_packmol.clicked.connect(self.stop_packmol_process)
        self.btn_stop_packmol.setEnabled(False)
        self.btn_stop_packmol.setStyleSheet("background-color: #f8d7da; color: red;")
        
        # --- NUEVO BOTÓN: VMD ---
        self.btn_view_vmd = QPushButton("👁 Ver en VMD")
        self.btn_view_vmd.clicked.connect(self.open_vmd)
        self.btn_view_vmd.setEnabled(False) # Se activa al finalizar Packmol
        self.btn_view_vmd.setStyleSheet("background-color: #cff4fc; color: black;")
        
        hbox_run.addWidget(self.btn_run_packmol)
        hbox_run.addWidget(self.btn_stop_packmol)
        hbox_run.addWidget(self.btn_view_vmd) # Añadido al layout

        layout.addWidget(self.btn_gen_input)
        layout.addLayout(hbox_run)
        layout.addStretch()
        self.setLayout(layout)

    # ... (Los métodos de tabla, cálculo y toggle_manual siguen igual) ...

    def add_component(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar Componente", "", "PDB/GRO (*.pdb *.gro)")
        if fname:
            row = self.table_comps.rowCount()
            self.table_comps.insertRow(row)
            self.table_comps.setItem(row, 0, QTableWidgetItem(os.path.basename(fname)))
            mw_calc = self.chem_tools.get_mw_from_pdb(fname)
            self.table_comps.setItem(row, 1, QTableWidgetItem(str(mw_calc)))
            self.table_comps.setItem(row, 2, QTableWidgetItem("100"))
            self.table_comps.setItem(row, 3, QTableWidgetItem("1000.0"))
            self.table_comps.setItem(row, 4, QTableWidgetItem(fname))

    def remove_component(self):
        row = self.table_comps.currentRow()
        if row >= 0: self.table_comps.removeRow(row)

    def get_molecules_from_table(self):
        molecules = []
        try:
            for row in range(self.table_comps.rowCount()):
                molecules.append({
                    'pdb': self.table_comps.item(row, 0).text(),
                    'full_path': self.table_comps.item(row, 4).text(),
                    'mw': float(self.table_comps.item(row, 1).text()),
                    'count': int(self.table_comps.item(row, 2).text()),
                    'density_kg_m3': float(self.table_comps.item(row, 3).text())
                })
            return molecules
        except ValueError:
            return []

    def toggle_manual_mode(self, checked):
        self.spin_box_size.setReadOnly(not checked)
        self.btn_calc.setEnabled(not checked)
        if checked:
            self.spin_box_size.setStyleSheet("background-color: white; color: black;")
        else:
            self.spin_box_size.setStyleSheet("font-weight: bold; color: blue;")

    def set_active_project(self, path):
        self.current_project_path = path
        self.btn_gen_input.setEnabled(True)

    def calculate_box(self):
        molecules = self.get_molecules_from_table()
        if not molecules: return
        try:
            margin = self.input_margin.value()
            size = self.chem_tools.calculate_box_size_mixing_rule(molecules, margin)
            self.spin_box_size.setValue(size)
        except ValueError:
            QMessageBox.warning(self, "Error", "Error en el cálculo.")

    def generate_input_file(self):
        if not self.current_project_path: return
        box_size = self.spin_box_size.value()
        if box_size <= 0: return

        molecules = self.get_molecules_from_table()
        storage_dir = os.path.join(self.current_project_path, "storage")
        os.makedirs(storage_dir, exist_ok=True)

        for mol in molecules:
            dest = os.path.join(storage_dir, mol['pdb'])
            try:
                shutil.copy(mol['full_path'], dest)
            except Exception: pass

        inp_path = os.path.join(storage_dir, "packmol.inp")
        out_pdb = "system_init.pdb"
        
        success, msg = self.chem_tools.generate_packmol_input(inp_path, out_pdb, box_size, molecules)
        
        if success:
            QMessageBox.information(self, "Éxito", f"Input generado. Lado: {box_size} Å")
            self.btn_run_packmol.setEnabled(True)
            self.btn_view_vmd.setEnabled(False) # Resetear VMD si generamos nuevo
        else:
            QMessageBox.critical(self, "Error", msg)

    def run_packmol_process(self):
        storage_dir = os.path.join(self.current_project_path, "storage")
        inp_file = os.path.join(storage_dir, "packmol.inp")
        if not os.path.exists(inp_file): return
        
        self.worker = CommandWorker(["packmol"], storage_dir, input_file_path=inp_file)
        self.worker.log_signal.connect(lambda s: print(f"PKM: {s}"))
        self.worker.finished_signal.connect(self.on_packmol_finished)
        
        self.btn_run_packmol.setEnabled(False)
        self.btn_gen_input.setEnabled(False)
        self.btn_stop_packmol.setEnabled(True)
        self.btn_view_vmd.setEnabled(False)
        self.worker.start()

    def stop_packmol_process(self):
        if self.worker: self.worker.stop_process()

    def on_packmol_finished(self, success, msg):
        self.btn_run_packmol.setEnabled(True)
        self.btn_gen_input.setEnabled(True)
        self.btn_stop_packmol.setEnabled(False)
        
        if success:
            QMessageBox.information(self, "Finalizado", "Estructura creada.")
            self.btn_view_vmd.setEnabled(True) # <--- Habilitar VMD si terminó bien
        else:
            QMessageBox.warning(self, "Aviso", msg)

    # --- NUEVA FUNCIÓN: ABRIR VMD ---
    def open_vmd(self):
        """Lanza VMD en segundo plano con el PDB generado"""
        if not self.current_project_path: return
        
        pdb_path = os.path.join(self.current_project_path, "storage", "system_init.pdb")
        
        if not os.path.exists(pdb_path):
            QMessageBox.warning(self, "Error", "No se encuentra el archivo system_init.pdb")
            return
            
        try:
            # Lanzamos VMD como un proceso independiente
            # Nota: Esto asume que 'vmd' está en el PATH del sistema
            subprocess.Popen(["vmd", pdb_path])
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "No se encontró el ejecutable 'vmd'.\nAsegúrese de tener VMD instalado y en el PATH.")
        except Exception as e:
            QMessageBox.critical(self, "Error al abrir VMD", str(e))

    def get_molecules_data(self):
        return self.get_molecules_from_table()