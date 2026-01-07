import os
import shutil
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QGroupBox, QFileDialog, QMessageBox, QHBoxLayout, 
    QSpinBox, QTableWidget, QTableWidgetItem, QHeaderView, 
    QAbstractItemView, QDoubleSpinBox, QCheckBox, QFormLayout
)
from src.model.chemistry_tools import ChemistryTools
from src.controller.workers import CommandWorker

class SetupTab(QWidget):
    def __init__(self):
        super().__init__()
        # Instancias de lógica de negocio
        self.chem_tools = ChemistryTools()
        
        # Estado del proyecto
        self.current_project_path = None
        
        # Worker para procesos en segundo plano
        self.worker = None
        
        # Inicializar Interfaz
        self.init_ui()

    def init_ui(self):
        """Construye la interfaz gráfica"""
        layout = QVBoxLayout()
        
        # ==========================================================
        # SECCIÓN 1: Composición del Sistema (Tabla)
        # ==========================================================
        group_mol = QGroupBox("1. Composición del Sistema")
        layout_mol = QVBoxLayout()
        
        # Tabla de componentes
        self.table_comps = QTableWidget()
        self.table_comps.setColumnCount(5)
        self.table_comps.setHorizontalHeaderLabels([
            "Archivo PDB", "MW (g/mol)", "Cant.", "Densidad (kg/m3)", "Ruta Oculta"
        ])
        
        # Ocultar la columna de la ruta completa para limpieza visual
        self.table_comps.setColumnHidden(4, True) 
        
        # Ajustes de estilo de tabla
        self.table_comps.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_comps.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        
        layout_mol.addWidget(self.table_comps)
        
        # Botones de gestión de tabla
        hbox_btns = QHBoxLayout()
        self.btn_add = QPushButton("➕ Agregar Componente")
        self.btn_add.clicked.connect(self.add_component_click)
        
        self.btn_remove = QPushButton("➖ Quitar Seleccionado")
        self.btn_remove.clicked.connect(self.remove_component)
        
        hbox_btns.addWidget(self.btn_add)
        hbox_btns.addWidget(self.btn_remove)
        layout_mol.addLayout(hbox_btns)
        
        group_mol.setLayout(layout_mol)
        layout.addWidget(group_mol)
        
        # ==========================================================
        # SECCIÓN 2: Dimensiones de la Caja
        # ==========================================================
        group_box = QGroupBox("2. Dimensiones de la Caja")
        form_box = QFormLayout()
        
        # Margen de seguridad
        self.input_margin = QSpinBox()
        self.input_margin.setRange(0, 200)
        self.input_margin.setValue(10)
        self.input_margin.setSuffix(" % (Margen)")
        self.input_margin.setToolTip("Porcentaje extra al volumen para evitar choques iniciales")
        
        # Botón de Cálculo
        self.btn_calc = QPushButton("Calcular Tamaño (Regla de Mezcla)")
        self.btn_calc.clicked.connect(self.calculate_box)
        
        # Checkbox Manual
        self.chk_manual = QCheckBox("Modo Manual (Sobrescribir cálculo)")
        self.chk_manual.toggled.connect(self.toggle_manual_mode)
        
        # Input de Resultado (Editable en modo manual)
        self.spin_box_size = QDoubleSpinBox()
        self.spin_box_size.setRange(0.0, 10000.0)
        self.spin_box_size.setDecimals(3)
        self.spin_box_size.setSuffix(" Å")
        self.spin_box_size.setReadOnly(True)
        self.spin_box_size.setStyleSheet("font-weight: bold; color: blue;")
        
        form_box.addRow("Margen de Expansión:", self.input_margin)
        form_box.addRow("", self.btn_calc)
        form_box.addRow("", self.chk_manual)
        form_box.addRow("Lado de Caja (Cúbica):", self.spin_box_size)
        
        group_box.setLayout(form_box)
        layout.addWidget(group_box)
        
        # ==========================================================
        # SECCIÓN 3: Ejecución (Packmol)
        # ==========================================================
        
        # Botón Generar Input
        self.btn_gen_input = QPushButton("1. Generar packmol.inp")
        self.btn_gen_input.clicked.connect(self.generate_input_file)
        self.btn_gen_input.setEnabled(False) # Se activa al cargar proyecto
        
        hbox_run = QHBoxLayout()
        
        # Botón Ejecutar
        self.btn_run_packmol = QPushButton("2. ▶ Ejecutar Packmol")
        self.btn_run_packmol.clicked.connect(self.run_packmol_process)
        self.btn_run_packmol.setEnabled(False)
        self.btn_run_packmol.setStyleSheet("background-color: #d1e7dd; color: black; font-weight: bold;")
        
        # Botón Detener
        self.btn_stop_packmol = QPushButton("⏹ Detener")
        self.btn_stop_packmol.clicked.connect(self.stop_packmol_process)
        self.btn_stop_packmol.setEnabled(False)
        self.btn_stop_packmol.setStyleSheet("background-color: #f8d7da; color: red;")
        
        # Botón VMD
        self.btn_view_vmd = QPushButton("👁 Ver en VMD")
        self.btn_view_vmd.clicked.connect(self.open_vmd)
        self.btn_view_vmd.setEnabled(False)
        self.btn_view_vmd.setStyleSheet("background-color: #cff4fc; color: black;")
        
        hbox_run.addWidget(self.btn_run_packmol)
        hbox_run.addWidget(self.btn_stop_packmol)
        hbox_run.addWidget(self.btn_view_vmd)

        layout.addWidget(self.btn_gen_input)
        layout.addLayout(hbox_run)
        
        layout.addStretch()
        self.setLayout(layout)

    # ==========================================================
    # LÓGICA DE NEGOCIO
    # ==========================================================

    def add_component_click(self):
        """Manejador del botón Agregar: Abre diálogo y luego inserta"""
        fname, _ = QFileDialog.getOpenFileName(self, "Seleccionar Componente", "", "PDB/GRO (*.pdb *.gro)")
        if fname:
            pdb_name = os.path.basename(fname)
            # Calcular Peso Molecular automáticamente desde el archivo
            mw = str(self.chem_tools.get_mw_from_pdb(fname))
            # Valores por defecto: Cantidad=100, Densidad=1000.0 (Agua aprox)
            self._insert_row_data(pdb_name, mw, "100", "1000.0", fname)

    def _insert_row_data(self, pdb, mw, count, dens, full_path):
        """Método interno para insertar datos en la tabla (Usado por GUI y por Cargar Proyecto)"""
        row = self.table_comps.rowCount()
        self.table_comps.insertRow(row)
        self.table_comps.setItem(row, 0, QTableWidgetItem(str(pdb)))
        self.table_comps.setItem(row, 1, QTableWidgetItem(str(mw)))
        self.table_comps.setItem(row, 2, QTableWidgetItem(str(count)))
        self.table_comps.setItem(row, 3, QTableWidgetItem(str(dens)))
        self.table_comps.setItem(row, 4, QTableWidgetItem(str(full_path)))

    def remove_component(self):
        """Elimina la fila seleccionada"""
        row = self.table_comps.currentRow()
        if row >= 0:
            self.table_comps.removeRow(row)

    def get_molecules_from_table(self):
        """Recopila la información de la tabla en una lista de diccionarios"""
        molecules = []
        try:
            for row in range(self.table_comps.rowCount()):
                molecules.append({
                    'pdb': self.table_comps.item(row, 0).text(),
                    'mw': float(self.table_comps.item(row, 1).text()),
                    'count': int(self.table_comps.item(row, 2).text()),
                    'density_kg_m3': float(self.table_comps.item(row, 3).text()),
                    'full_path': self.table_comps.item(row, 4).text()
                })
            return molecules
        except ValueError:
            return []

    def toggle_manual_mode(self, checked):
        """Activa/Desactiva la edición manual de la caja"""
        self.spin_box_size.setReadOnly(not checked)
        self.btn_calc.setEnabled(not checked)
        
        if checked:
            self.spin_box_size.setStyleSheet("background-color: white; color: black;")
        else:
            self.spin_box_size.setStyleSheet("font-weight: bold; color: blue;")

    def set_active_project(self, path):
        """Recibe la ruta del proyecto activo desde MainWindow"""
        self.current_project_path = path
        self.btn_gen_input.setEnabled(True)

    def calculate_box(self):
        """Calcula el tamaño de la caja usando la Regla de Mezcla"""
        molecules = self.get_molecules_from_table()
        if not molecules:
            QMessageBox.warning(self, "Aviso", "La tabla está vacía o tiene datos inválidos.")
            return
        
        try:
            margin = self.input_margin.value()
            size = self.chem_tools.calculate_box_size_mixing_rule(molecules, margin)
            self.spin_box_size.setValue(size)
        except ValueError:
            QMessageBox.warning(self, "Error", "Error en el cálculo. Verifique los valores numéricos.")

    def generate_input_file(self):
        """Genera packmol.inp y copia los PDBs a la carpeta storage"""
        if not self.current_project_path:
            return
            
        box_size = self.spin_box_size.value()
        if box_size <= 0:
            QMessageBox.warning(self, "Error", "El tamaño de la caja debe ser mayor a 0.")
            return

        molecules = self.get_molecules_from_table()
        if not molecules:
            QMessageBox.warning(self, "Error", "La tabla de componentes está vacía.")
            return

        # Asegurar directorio de almacenamiento
        storage_dir = os.path.join(self.current_project_path, "storage")
        os.makedirs(storage_dir, exist_ok=True)

        # Copiar PDBs originales a la carpeta del proyecto
        for mol in molecules:
            dest = os.path.join(storage_dir, mol['pdb'])
            try:
                shutil.copy(mol['full_path'], dest)
            except Exception:
                pass # Si falla copia (ej. mismo archivo), seguimos

        inp_path = os.path.join(storage_dir, "packmol.inp")
        out_pdb = "system_init.pdb"
        
        # Llamar al modelo para escribir archivo
        success, msg = self.chem_tools.generate_packmol_input(inp_path, out_pdb, box_size, molecules)
        
        if success:
            QMessageBox.information(self, "Éxito", f"Input generado correctamente.\nLado de caja: {box_size} Å")
            self.btn_run_packmol.setEnabled(True)
            self.btn_view_vmd.setEnabled(False) # Desactivar VMD hasta que se ejecute nuevo packmol
        else:
            QMessageBox.critical(self, "Error", msg)

    def run_packmol_process(self):
        """Ejecuta Packmol en un hilo separado"""
        storage_dir = os.path.join(self.current_project_path, "storage")
        inp_file = os.path.join(storage_dir, "packmol.inp")
        
        if not os.path.exists(inp_file):
            QMessageBox.warning(self, "Error", "No se encontró el archivo packmol.inp")
            return
        
        # Configurar Worker (Hilo secundario)
        self.worker = CommandWorker(["packmol"], storage_dir, input_file_path=inp_file)
        self.worker.log_signal.connect(lambda s: print(f"PKM: {s}"))
        self.worker.finished_signal.connect(self.on_packmol_finished)
        
        # Ajustar estado de botones durante ejecución
        self.btn_run_packmol.setEnabled(False)
        self.btn_gen_input.setEnabled(False)
        self.btn_stop_packmol.setEnabled(True)
        self.btn_view_vmd.setEnabled(False)
        
        self.worker.start()

    def stop_packmol_process(self):
        """Detiene la ejecución de Packmol"""
        if self.worker:
            self.worker.stop_process()

    def on_packmol_finished(self, success, msg):
        """Callback al terminar Packmol"""
        # Restaurar botones
        self.btn_run_packmol.setEnabled(True)
        self.btn_gen_input.setEnabled(True)
        self.btn_stop_packmol.setEnabled(False)
        
        if success:
            QMessageBox.information(self, "Finalizado", "Estructura creada correctamente.")
            self.btn_view_vmd.setEnabled(True)
        else:
            QMessageBox.warning(self, "Aviso", f"Packmol terminó con problemas:\n{msg}")

    def open_vmd(self):
        """Abre VMD para visualizar el resultado"""
        if not self.current_project_path: return
        
        pdb_path = os.path.join(self.current_project_path, "storage", "system_init.pdb")
        if not os.path.exists(pdb_path):
            QMessageBox.warning(self, "Error", "No existe system_init.pdb")
            return
            
        try:
            subprocess.Popen(["vmd", pdb_path])
        except Exception as e:
            QMessageBox.critical(self, "Error VMD", f"No se pudo iniciar VMD:\n{e}")

    # ==========================================================
    # MÉTODOS DE ACCESO PÚBLICO (Para otras pestañas)
    # ==========================================================
    
    def get_box_size_value(self):
        """Retorna el tamaño de caja actual (usado por Topology Tab)"""
        return self.spin_box_size.value()
    
    def get_molecules_data(self):
        """Retorna la lista de moléculas (usado por Topology Tab)"""
        return self.get_molecules_from_table()

    # ==========================================================
    # PERSISTENCIA (GUARDAR Y CARGAR ESTADO)
    # ==========================================================
    
    def get_state(self):
        """Devuelve diccionario con el estado actual para guardar en JSON"""
        return {
            "molecules": self.get_molecules_from_table(),
            "margin": self.input_margin.value(),
            "manual_mode": self.chk_manual.isChecked(),
            "box_size": self.spin_box_size.value()
        }

    def set_state(self, state):
        """Restaura el estado desde diccionario cargado de JSON"""
        if not state: return
        
        self.input_margin.setValue(state.get("margin", 10))
        self.chk_manual.setChecked(state.get("manual_mode", False))
        self.spin_box_size.setValue(state.get("box_size", 0.0))
        
        # Restaurar tabla usando el método interno (sin ventanas emergentes)
        mols = state.get("molecules", [])
        self.table_comps.setRowCount(0)
        for mol in mols:
            self._insert_row_data(
                mol.get('pdb', ''),
                mol.get('mw', 0),
                mol.get('count', 0),
                mol.get('density_kg_m3', 0),
                mol.get('full_path', '')
            )