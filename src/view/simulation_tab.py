import os
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QTextEdit, QGroupBox, 
                             QLineEdit, QSpinBox, QDoubleSpinBox, QMessageBox, 
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QTabWidget, QFormLayout, QCheckBox)
from PyQt6.QtCore import Qt
from src.model.mdp_manager import MdpManager
from src.controller.workers import CommandWorker

class SimulationTab(QWidget):
    def __init__(self):
        super().__init__()
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        templates_path = os.path.join(base_dir, "assets", "templates")
        
        self.mdp_mgr = MdpManager(templates_path)
        self.project_mgr = None
        self.current_project_path = None
        self.worker = None 
        self.protocol_steps = []
        
        # Variable para evitar bucles de actualización
        self.is_updating_ui = False
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- 1. CONSTRUCTOR DE PROTOCOLO ---
        group_proto = QGroupBox("1. Constructor de Protocolo")
        layout_proto = QVBoxLayout()
        
        hbox_add = QHBoxLayout()
        self.combo_type = QComboBox()
        self.combo_type.addItems(["minim", "nvt", "npt", "prod"])
        self.input_step_name = QLineEdit()
        self.input_step_name.setPlaceholderText("Nombre único (ej: npt_suave)")
        btn_add = QPushButton("➕ Agregar"); btn_add.clicked.connect(self.add_step)
        btn_del = QPushButton("➖ Eliminar"); btn_del.clicked.connect(self.remove_step)
        
        hbox_add.addWidget(QLabel("Tipo:")); hbox_add.addWidget(self.combo_type)
        hbox_add.addWidget(QLabel("Nombre:")); hbox_add.addWidget(self.input_step_name)
        hbox_add.addWidget(btn_add); hbox_add.addWidget(btn_del)
        layout_proto.addLayout(hbox_add)
        
        self.table_steps = QTableWidget()
        self.table_steps.setColumnCount(4)
        self.table_steps.setHorizontalHeaderLabels(["#", "Nombre", "Tipo", "Estado"])
        self.table_steps.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_steps.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_steps.cellClicked.connect(self.on_step_selected)
        layout_proto.addWidget(self.table_steps)
        group_proto.setLayout(layout_proto)
        layout.addWidget(group_proto)
        
        # --- 2. CONFIGURACIÓN (NUEVO SISTEMA DE TABS) ---
        group_edit = QGroupBox("2. Configuración del Paso")
        layout_edit = QVBoxLayout()
        
        self.lbl_editing = QLabel("Seleccione un paso para editar...")
        self.lbl_editing.setStyleSheet("color: blue; font-weight: bold;")
        layout_edit.addWidget(self.lbl_editing)
        
        # Tabs de Configuración
        self.config_tabs = QTabWidget()
        
        # -- Tab A: Básico --
        self.tab_basic = QWidget()
        self.init_basic_ui()
        self.config_tabs.addTab(self.tab_basic, "Básico (General)")
        
        # -- Tab B: Avanzado --
        self.tab_adv = QWidget()
        self.init_advanced_ui()
        self.config_tabs.addTab(self.tab_adv, "Avanzado (Físico)")
        
        # -- Tab C: Experto (Texto) --
        self.tab_expert = QWidget()
        layout_expert = QVBoxLayout()
        self.text_editor = QTextEdit()
        self.text_editor.setPlaceholderText("Vista previa del archivo MDP...")
        self.text_editor.setStyleSheet("font-family: Monospace; font-size: 11px;")
        # Si editan el texto manual, asumimos modo experto
        layout_expert.addWidget(self.text_editor)
        self.tab_expert.setLayout(layout_expert)
        self.config_tabs.addTab(self.tab_expert, "Experto (Código Fuente)")
        
        layout_edit.addWidget(self.config_tabs)
        
        # Botón Guardar Global
        self.btn_save_mdp = QPushButton("💾 Guardar Cambios en .mdp")
        self.btn_save_mdp.clicked.connect(self.save_current_mdp)
        self.btn_save_mdp.setEnabled(False)
        layout_edit.addWidget(self.btn_save_mdp)
        
        group_edit.setLayout(layout_edit)
        layout.addWidget(group_edit)
        
        # --- 3. EJECUCIÓN ---
        group_run = QGroupBox("3. Motor de Ejecución")
        layout_run = QVBoxLayout()
        hbox_run = QHBoxLayout()
        
        self.btn_grompp = QPushButton("Compilar (grompp)")
        self.btn_grompp.clicked.connect(self.run_grompp)
        self.btn_grompp.setEnabled(False)
        
        self.btn_mdrun = QPushButton("Correr (mdrun)")
        self.btn_mdrun.clicked.connect(self.run_mdrun)
        self.btn_mdrun.setEnabled(False)
        
        self.btn_stop = QPushButton("Detener")
        self.btn_stop.clicked.connect(self.stop_simulation)
        self.btn_stop.setEnabled(False); self.btn_stop.setStyleSheet("color: red;")
        
        hbox_run.addWidget(self.btn_grompp); hbox_run.addWidget(self.btn_mdrun); hbox_run.addWidget(self.btn_stop)
        layout_run.addLayout(hbox_run)
        group_run.setLayout(layout_run)
        layout.addWidget(group_run)
        
        self.setLayout(layout)

    # --- UI INIT METHODS ---
    
    def init_basic_ui(self):
        layout = QFormLayout()
        
        # Temperatura
        self.spin_temp = QDoubleSpinBox(); self.spin_temp.setRange(0, 2000); self.spin_temp.setSuffix(" K")
        self.spin_temp.valueChanged.connect(self.sync_gui_to_text)
        
        # Presión
        self.spin_press = QDoubleSpinBox(); self.spin_press.setRange(0, 1000); self.spin_press.setSuffix(" bar")
        self.spin_press.valueChanged.connect(self.sync_gui_to_text)
        
        # Tiempo (ns) - Conversor automático a nsteps
        self.spin_time_ns = QDoubleSpinBox(); self.spin_time_ns.setRange(0, 10000); self.spin_time_ns.setSingleStep(0.1); self.spin_time_ns.setSuffix(" ns")
        self.spin_time_ns.valueChanged.connect(self.on_time_changed)
        
        # Pasos (Readonly o editable, mejor dejarlo informativo)
        self.lbl_steps_calc = QLabel("Pasos: 0 (Calculado)")
        
        layout.addRow("Temperatura:", self.spin_temp)
        layout.addRow("Presión:", self.spin_press)
        layout.addRow("Duración:", self.spin_time_ns)
        layout.addRow("", self.lbl_steps_calc)
        
        self.tab_basic.setLayout(layout)

    def init_advanced_ui(self):
        layout = QFormLayout()
        
        # Integrador
        self.combo_integrator = QComboBox()
        self.combo_integrator.addItems(["md (Leap-frog)", "steep (Minimización)", "sd (Langevin)"])
        self.combo_integrator.currentIndexChanged.connect(self.sync_gui_to_text)
        
        # Paso de tiempo (dt)
        self.spin_dt = QDoubleSpinBox(); self.spin_dt.setRange(0.0001, 0.010); self.spin_dt.setDecimals(4); self.spin_dt.setSuffix(" ps")
        self.spin_dt.setValue(0.002)
        self.spin_dt.valueChanged.connect(self.on_dt_changed) # Recalcula tiempo
        
        # Termostato
        self.combo_tcoupl = QComboBox()
        self.combo_tcoupl.addItems(["V-rescale", "Nose-Hoover", "Berendsen", "no"])
        self.combo_tcoupl.currentIndexChanged.connect(self.sync_gui_to_text)
        
        # Barostato
        self.combo_pcoupl = QComboBox()
        self.combo_pcoupl.addItems(["Parrinello-Rahman", "C-rescale", "Berendsen", "no"])
        self.combo_pcoupl.currentIndexChanged.connect(self.sync_gui_to_text)
        
        # Restricciones
        self.combo_constraints = QComboBox()
        self.combo_constraints.addItems(["h-bonds", "all-bonds", "none"])
        self.combo_constraints.currentIndexChanged.connect(self.sync_gui_to_text)
        
        layout.addRow("Integrador:", self.combo_integrator)
        layout.addRow("Paso de Tiempo (dt):", self.spin_dt)
        layout.addRow("Termostato:", self.combo_tcoupl)
        layout.addRow("Barostato:", self.combo_pcoupl)
        layout.addRow("Restricciones:", self.combo_constraints)
        
        self.tab_adv.setLayout(layout)

    # --- LÓGICA DE SINCRONIZACIÓN ---
    
    def on_time_changed(self):
        """Calcula nsteps basado en Tiempo(ns) y dt"""
        if self.is_updating_ui: return
        
        ns = self.spin_time_ns.value()
        dt_ps = self.spin_dt.value()
        
        # 1 ns = 1000 ps
        total_ps = ns * 1000.0
        nsteps = int(total_ps / dt_ps)
        
        self.lbl_steps_calc.setText(f"Pasos: {nsteps}")
        self.sync_gui_to_text(nsteps_override=nsteps)

    def on_dt_changed(self):
        """Si cambia dt, recalcula steps manteniendo el tiempo en ns"""
        self.on_time_changed()

    def sync_gui_to_text(self, nsteps_override=None):
        """Toma valores de GUI y actualiza el texto MDP en tiempo real"""
        if self.is_updating_ui: return
        
        # Mapa de valores
        params = {}
        
        # Básico
        params['ref_t'] = self.spin_temp.value()
        params['gen_temp'] = self.spin_temp.value()
        params['ref_p'] = self.spin_press.value()
        
        if nsteps_override:
            params['nsteps'] = nsteps_override
        
        # Avanzado
        # Extraemos el valor limpio del combo (ej "md (Leap-frog)" -> "md")
        params['integrator'] = self.combo_integrator.currentText().split()[0]
        params['dt'] = self.spin_dt.value()
        params['tcoupl'] = self.combo_tcoupl.currentText()
        params['pcoupl'] = self.combo_pcoupl.currentText()
        params['constraints'] = self.combo_constraints.currentText()
        
        # Actualizar texto usando el Manager
        current_text = self.text_editor.toPlainText()
        new_text = self.mdp_mgr.update_parameters(current_text, params)
        
        # Evitar disparo recursivo de señales
        self.is_updating_ui = True
        self.text_editor.setPlainText(new_text)
        self.is_updating_ui = False

    def on_step_selected(self, row, col):
        """Carga datos y ajusta la GUI según el tipo de paso"""
        if row < 0 or not self.current_project_path: return
        
        self.is_updating_ui = True # Pausar sync
        
        step = self.protocol_steps[row]
        self.lbl_editing.setText(f"Editando: {step['name']} ({step['type']})")
        
        # 1. Cargar Texto MDP
        storage_dir = os.path.join(self.current_project_path, "storage")
        mdp_path = os.path.join(storage_dir, f"{step['name']}.mdp")
        
        if os.path.exists(mdp_path):
            with open(mdp_path, 'r') as f: content = f.read()
        else:
            content = self.mdp_mgr.get_template_content(step['type'])
        
        self.text_editor.setPlainText(content)
        
        # 2. Parsear valores inversos (Texto -> GUI) para mostrar en controles
        # Esto es complejo hacerlo perfecto con regex, así que usamos valores por defecto
        # o implementamos un parser simple si es crítico. 
        # Para simplificar: Seteamos valores "sugeridos" según el tipo
        
        if step['type'] == 'minim':
            self.spin_time_ns.setEnabled(False) # Minimización no tiene tiempo en ns
            self.combo_integrator.setCurrentIndex(1) # steep
            self.spin_press.setEnabled(False)
        else:
            self.spin_time_ns.setEnabled(True)
            self.combo_integrator.setCurrentIndex(0) # md
            self.spin_press.setEnabled(True)
            
            # Defaults típicos
            if step['type'] == 'nvt':
                self.spin_time_ns.setValue(0.1) # 100ps
                self.combo_pcoupl.setCurrentIndex(3) # no
            elif step['type'] == 'npt':
                self.spin_time_ns.setValue(0.1)
                self.combo_pcoupl.setCurrentIndex(1) # C-rescale
            elif step['type'] == 'prod':
                self.spin_time_ns.setValue(1.0) # 1ns
                self.combo_pcoupl.setCurrentIndex(0) # Parrinello

        self.btn_save_mdp.setEnabled(True)
        self.btn_grompp.setEnabled(True)
        self.btn_mdrun.setEnabled(False)
        
        self.is_updating_ui = False
        
        # Forzar una actualización Texto -> GUI (parcial) o GUI -> Texto
        # En este diseño, la GUI sobrescribe el texto al cambiar valores, 
        # así que el usuario ve la plantilla base modificada por los valores de la GUI.
        self.sync_gui_to_text()

    # --- GESTIÓN DE PROTOCOLO ---
    def add_step(self):
        step_type = self.combo_type.currentText()
        custom_name = self.input_step_name.text().strip()
        if not custom_name:
            count = len([s for s in self.protocol_steps if s['type'] == step_type]) + 1
            custom_name = f"{step_type}_{count}"
        
        if any(s['name'] == custom_name for s in self.protocol_steps):
            QMessageBox.warning(self, "Error", "Nombre duplicado.")
            return

        self.protocol_steps.append({'type': step_type, 'name': custom_name, 'status': 'Pendiente'})
        self.refresh_table()

    def remove_step(self):
        row = self.table_steps.currentRow()
        if row >= 0:
            self.protocol_steps.pop(row)
            self.refresh_table()

    def refresh_table(self):
        self.table_steps.setRowCount(len(self.protocol_steps))
        for i, step in enumerate(self.protocol_steps):
            self.table_steps.setItem(i, 0, QTableWidgetItem(str(i+1)))
            self.table_steps.setItem(i, 1, QTableWidgetItem(step['name']))
            self.table_steps.setItem(i, 2, QTableWidgetItem(step['type']))
            
            status_item = QTableWidgetItem(step['status'])
            if step['status'] == 'Completado': status_item.setForeground(Qt.GlobalColor.green)
            elif step['status'] == 'Error': status_item.setForeground(Qt.GlobalColor.red)
            self.table_steps.setItem(i, 3, status_item)

    # --- PERSISTENCIA Y EJECUCIÓN ---
    def update_project_data(self, project_mgr):
        self.project_mgr = project_mgr
        self.current_project_path = project_mgr.current_project_path

    def save_current_mdp(self):
        row = self.table_steps.currentRow()
        if row < 0 or not self.current_project_path: return
        step_name = self.protocol_steps[row]['name']
        filename = f"{step_name}.mdp"
        path = os.path.join(self.current_project_path, "storage", filename)
        
        # Guardamos lo que haya en el editor de texto (que es lo final)
        success, msg = self.mdp_mgr.save_mdp(path, self.text_editor.toPlainText())
        if success:
            QMessageBox.information(self, "Guardado", f"Archivo actualizado: {filename}")
        else:
            QMessageBox.critical(self, "Error", msg)

    # --- RUNNER (Identico a versión anterior, resumido) ---
    def get_chain_files(self, row_index):
        step = self.protocol_steps[row_index]
        storage_dir = os.path.join(self.current_project_path, "storage")
        
        if row_index == 0: input_gro = "system.gro"
        else:
            prev_name = self.protocol_steps[row_index - 1]['name']
            input_gro = f"{prev_name}.gro"
            if not os.path.exists(os.path.join(storage_dir, input_gro)):
                QMessageBox.warning(self, "Bloqueo", f"Falta el resultado de: {prev_name}")
                return None
        return f"{step['name']}.mdp", input_gro, f"{step['name']}.tpr"

    def run_grompp(self):
        row = self.table_steps.currentRow()
        if row < 0: return
        files = self.get_chain_files(row)
        if not files: return
        mdp, gro, tpr = files
        storage_dir = os.path.join(self.current_project_path, "storage")
        
        if not os.path.exists(os.path.join(storage_dir, mdp)):
            QMessageBox.warning(self, "Aviso", "Guarde el MDP primero.")
            return

        cmd = ["gmx", "grompp", "-f", mdp, "-c", gro, "-p", "topol.top", "-o", tpr, "-maxwarn", "2"]
        self.worker = CommandWorker(cmd, storage_dir)
        self.worker.log_signal.connect(lambda s: print(f"GROMPP: {s}"))
        self.worker.finished_signal.connect(self.on_grompp_finished)
        self.btn_grompp.setEnabled(False)
        self.worker.start()

    def on_grompp_finished(self, success, msg):
        self.btn_grompp.setEnabled(True)
        if success: 
            QMessageBox.information(self, "Éxito", "TPR generado.")
            self.btn_mdrun.setEnabled(True)
        else: QMessageBox.critical(self, "Error", msg)

    def run_mdrun(self):
        row = self.table_steps.currentRow()
        step_name = self.protocol_steps[row]['name']
        storage_dir = os.path.join(self.current_project_path, "storage")
        if not os.path.exists(os.path.join(storage_dir, f"{step_name}.tpr")): return
        
        cmd = ["gmx", "mdrun", "-deffnm", step_name]
        self.worker = CommandWorker(cmd, storage_dir)
        self.worker.log_signal.connect(lambda s: print(f"MDRUN: {s}"))
        self.worker.finished_signal.connect(self.on_mdrun_finished)
        self.btn_grompp.setEnabled(False); self.btn_mdrun.setEnabled(False); self.btn_stop.setEnabled(True)
        self.protocol_steps[row]['status'] = 'Corriendo...'
        self.refresh_table()
        self.worker.start()

    def stop_simulation(self):
        if self.worker: self.worker.stop_process()

    def on_mdrun_finished(self, success, msg):
        row = self.table_steps.currentRow()
        self.btn_grompp.setEnabled(True); self.btn_mdrun.setEnabled(True); self.btn_stop.setEnabled(False)
        self.protocol_steps[row]['status'] = 'Completado' if success else 'Error'
        self.refresh_table()
        if success: QMessageBox.information(self, "Fin", "Simulación terminada.")
        else: QMessageBox.warning(self, "Error", msg)