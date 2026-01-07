import os
import re
import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QTextEdit, QGroupBox, 
    QLineEdit, QSpinBox, QDoubleSpinBox, QMessageBox, 
    QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView, # <--- Cambio Importante
    QTabWidget, QFormLayout, QLCDNumber, QProgressBar, QMenu
)
from PyQt6.QtCore import Qt, QTimer
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
        
        # Ya no usamos una lista plana self.protocol_steps
        # La "verdad" ahora reside en la estructura visual del QTreeWidget
        
        self.is_updating_ui = False
        
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_elapsed_time)
        self.elapsed_seconds_counter = 0
        self.total_steps_target = 0
        self.start_time_wall = None
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- 1. ÁRBOL DE PROTOCOLO ---
        group_proto = QGroupBox("1. Árbol de Simulación (Ramificación)")
        layout_proto = QVBoxLayout()
        
        hbox_add = QHBoxLayout()
        self.combo_type = QComboBox(); self.combo_type.addItems(["minim", "nvt", "npt", "prod"])
        self.input_step_name = QLineEdit(); self.input_step_name.setPlaceholderText("Nombre del paso")
        
        # Botones modificados para lógica de árbol
        btn_add_child = QPushButton("➕ Agregar Hijo")
        btn_add_child.setToolTip("Agrega un paso derivado del nodo seleccionado")
        btn_add_child.clicked.connect(self.add_step_child)
        
        btn_del = QPushButton("➖ Eliminar Rama")
        btn_del.clicked.connect(self.remove_branch)
        
        hbox_add.addWidget(QLabel("Tipo:")); hbox_add.addWidget(self.combo_type)
        hbox_add.addWidget(QLabel("Nombre:")); hbox_add.addWidget(self.input_step_name)
        hbox_add.addWidget(btn_add_child); hbox_add.addWidget(btn_del)
        
        # TREE WIDGET
        self.tree_steps = QTreeWidget()
        self.tree_steps.setHeaderLabels(["Nombre (ID)", "Tipo", "Estado"])
        self.tree_steps.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_steps.itemClicked.connect(self.on_node_selected)
        
        layout_proto.addLayout(hbox_add)
        layout_proto.addWidget(self.tree_steps)
        group_proto.setLayout(layout_proto); layout.addWidget(group_proto)
        
        # --- 2. CONFIGURACIÓN ---
        group_edit = QGroupBox("2. Configuración del Paso Seleccionado")
        layout_edit = QVBoxLayout()
        self.lbl_editing = QLabel("Seleccione un nodo del árbol...")
        self.lbl_editing.setStyleSheet("color: blue; font-weight: bold;")
        layout_edit.addWidget(self.lbl_editing)
        
        self.config_tabs = QTabWidget()
        self.tab_basic = QWidget(); self.init_basic_ui(); self.config_tabs.addTab(self.tab_basic, "Básico")
        self.tab_adv = QWidget(); self.init_advanced_ui(); self.config_tabs.addTab(self.tab_adv, "Avanzado")
        self.tab_expert = QWidget(); l_exp = QVBoxLayout(); self.text_editor = QTextEdit(); self.text_editor.setStyleSheet("font-family: monospace")
        l_exp.addWidget(self.text_editor); self.tab_expert.setLayout(l_exp); self.config_tabs.addTab(self.tab_expert, "Experto")
        layout_edit.addWidget(self.config_tabs)
        
        self.btn_save_mdp = QPushButton("💾 Guardar MDP"); self.btn_save_mdp.clicked.connect(self.save_current_mdp); self.btn_save_mdp.setEnabled(False)
        layout_edit.addWidget(self.btn_save_mdp)
        group_edit.setLayout(layout_edit); layout.addWidget(group_edit)
        
        # --- 3. MONITOR ---
        group_run = QGroupBox("3. Monitor de Ejecución")
        layout_run = QVBoxLayout()
        hbox_run = QHBoxLayout()
        
        self.btn_grompp = QPushButton("Compilar"); self.btn_grompp.clicked.connect(self.run_grompp); self.btn_grompp.setEnabled(False)
        self.btn_mdrun = QPushButton("▶ Correr"); self.btn_mdrun.clicked.connect(self.run_mdrun); self.btn_mdrun.setEnabled(False)
        self.btn_stop = QPushButton("⏹ Detener"); self.btn_stop.clicked.connect(self.stop_simulation); self.btn_stop.setEnabled(False); self.btn_stop.setStyleSheet("color: red")
        
        hbox_run.addWidget(self.btn_grompp); hbox_run.addWidget(self.btn_mdrun); hbox_run.addWidget(self.btn_stop)
        
        hbox_info = QHBoxLayout()
        self.lbl_elapsed = QLabel("Transcurrido: 00:00:00")
        self.lbl_eta = QLabel("Estimación: --:--")
        self.lbl_eta.setStyleSheet("color: blue; font-weight: bold")
        hbox_info.addWidget(self.lbl_elapsed); hbox_info.addStretch(); hbox_info.addWidget(self.lbl_eta)
        
        layout_run.addLayout(hbox_run); layout_run.addLayout(hbox_info)
        group_run.setLayout(layout_run); layout.addWidget(group_run)
        
        self.setLayout(layout)

    # --- UI INIT HELPERS ---
    def init_basic_ui(self):
        l = QFormLayout()
        self.spin_temp = QDoubleSpinBox(); self.spin_temp.setRange(0,2000); self.spin_temp.valueChanged.connect(self.sync)
        self.spin_press = QDoubleSpinBox(); self.spin_press.setRange(0,1000); self.spin_press.valueChanged.connect(self.sync)
        self.spin_time = QDoubleSpinBox(); self.spin_time.setRange(0,10000); self.spin_time.valueChanged.connect(self.sync_time)
        self.lbl_steps = QLabel("0")
        l.addRow("Temp (K):", self.spin_temp); l.addRow("Pres (bar):", self.spin_press); l.addRow("Tiempo (ns):", self.spin_time); l.addRow("Pasos:", self.lbl_steps)
        self.tab_basic.setLayout(l)

    def init_advanced_ui(self):
        l = QFormLayout()
        self.c_int = QComboBox(); self.c_int.addItems(["md", "steep", "sd"]); self.c_int.currentIndexChanged.connect(self.sync)
        self.s_dt = QDoubleSpinBox(); self.s_dt.setRange(0,0.1); self.s_dt.setDecimals(4); self.s_dt.setValue(0.002); self.s_dt.valueChanged.connect(self.sync_time)
        self.c_t = QComboBox(); self.c_t.addItems(["V-rescale", "Nose-Hoover", "no"]); self.c_t.currentIndexChanged.connect(self.sync)
        self.c_p = QComboBox(); self.c_p.addItems(["Parrinello-Rahman", "C-rescale", "no"]); self.c_p.currentIndexChanged.connect(self.sync)
        l.addRow("Integrador:", self.c_int); l.addRow("dt (ps):", self.s_dt); l.addRow("Termostato:", self.c_t); l.addRow("Barostato:", self.c_p)
        self.tab_adv.setLayout(l)

    # --- SYNC LOGIC ---
    def sync_time(self):
        if self.is_updating_ui: return
        nsteps = int((self.spin_time.value() * 1000) / self.s_dt.value()) if self.s_dt.value() > 0 else 0
        self.lbl_steps.setText(str(nsteps))
        self.sync(nsteps)

    def sync(self, nsteps=None):
        if self.is_updating_ui: return
        p = {'ref_t': self.spin_temp.value(), 'gen_temp': self.spin_temp.value(), 'ref_p': self.spin_press.value(),
             'integrator': self.c_int.currentText(), 'dt': self.s_dt.value(), 
             'tcoupl': self.c_t.currentText(), 'pcoupl': self.c_p.currentText()}
        if nsteps: p['nsteps'] = nsteps
        self.is_updating_ui = True
        self.text_editor.setPlainText(self.mdp_mgr.update_parameters(self.text_editor.toPlainText(), p))
        self.is_updating_ui = False

    # ============================================================
    # GESTIÓN DEL ÁRBOL (BRANCHING)
    # ============================================================
    
    def add_step_child(self):
        # 1. Obtener nodo padre seleccionado
        current_item = self.tree_steps.currentItem()
        
        # Si no hay nada seleccionado, el padre es "Root" (System)
        # Pero visualmente los pondremos en el nivel superior
        parent_item = current_item if current_item else self.tree_steps.invisibleRootItem()
        
        step_type = self.combo_type.currentText()
        name = self.input_step_name.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Error", "Escriba un nombre único para el paso.")
            return
            
        # Validar duplicados (recursivo o global)
        # Por simplicidad, validamos globalmente en el directorio storage
        if self.current_project_path:
            if os.path.exists(os.path.join(self.current_project_path, "storage", f"{name}.mdp")):
                QMessageBox.warning(self, "Error", f"El nombre '{name}' ya existe en el proyecto.")
                return

        # Crear Nodo
        item = QTreeWidgetItem(parent_item)
        item.setText(0, name)
        item.setText(1, step_type)
        item.setText(2, "Pendiente")
        
        # Expandir padre para ver el hijo
        if current_item: current_item.setExpanded(True)
        self.input_step_name.clear()

    def remove_branch(self):
        item = self.tree_steps.currentItem()
        if not item: return
        
        reply = QMessageBox.question(self, "Eliminar", f"¿Eliminar '{item.text(0)}' y sus hijos?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            (item.parent() or self.tree_steps.invisibleRootItem()).removeChild(item)

    def on_node_selected(self, item, col):
        if not self.current_project_path: return
        self.is_updating_ui = True
        
        name = item.text(0)
        sType = item.text(1)
        self.lbl_editing.setText(f"Editando: {name} (Hijo de: {item.parent().text(0) if item.parent() else 'Sistema'})")
        
        path = os.path.join(self.current_project_path, "storage", f"{name}.mdp")
        content = open(path).read() if os.path.exists(path) else self.mdp_mgr.get_template_content(sType)
        self.text_editor.setPlainText(content)
        
        # Defaults
        is_min = sType == 'minim'
        self.spin_time.setEnabled(not is_min); self.spin_press.setEnabled(not is_min)
        if is_min: self.c_int.setCurrentIndex(1)
        else: self.c_int.setCurrentIndex(0)
        
        self.btn_save_mdp.setEnabled(True); self.btn_grompp.setEnabled(True); self.btn_mdrun.setEnabled(False)
        self.is_updating_ui = False; self.sync()

    # ============================================================
    # PERSISTENCIA RECURSIVA (ÁRBOL -> JSON -> ÁRBOL)
    # ============================================================
    
    def get_state(self):
        """Convierte el árbol visual a una estructura de lista recursiva"""
        def serialize_item(item):
            node = {
                "name": item.text(0),
                "type": item.text(1),
                "status": item.text(2),
                "children": []
            }
            for i in range(item.childCount()):
                node["children"].append(serialize_item(item.child(i)))
            return node

        root = self.tree_steps.invisibleRootItem()
        tree_data = [serialize_item(root.child(i)) for i in range(root.childCount())]
        return {"tree_data": tree_data}

    def set_state(self, state):
        if not state: return
        self.tree_steps.clear()
        
        def deserialize_item(node_data, parent):
            item = QTreeWidgetItem(parent)
            item.setText(0, node_data["name"])
            item.setText(1, node_data["type"])
            st = node_data.get("status", "Pendiente")
            item.setText(2, st)
            
            # Colores
            if st == 'Completado': item.setForeground(2, Qt.GlobalColor.green)
            elif st == 'Error': item.setForeground(2, Qt.GlobalColor.red)
            
            for child_data in node_data.get("children", []):
                deserialize_item(child_data, item)
            item.setExpanded(True)

        for node in state.get("tree_data", []):
            deserialize_item(node, self.tree_steps)

    def update_project_data(self, mgr):
        self.project_mgr = mgr; self.current_project_path = mgr.current_project_path

    # ============================================================
    # EJECUCIÓN CON RAMIFICACIÓN
    # ============================================================

    def save_current_mdp(self):
        item = self.tree_steps.currentItem()
        if not item: return
        path = os.path.join(self.current_project_path, "storage", f"{item.text(0)}.mdp")
        if self.mdp_mgr.save_mdp(path, self.text_editor.toPlainText())[0]:
            QMessageBox.information(self, "OK", "Guardado")

    def run_grompp(self):
        item = self.tree_steps.currentItem()
        if not item: return
        
        current_name = item.text(0)
        parent_item = item.parent()
        
        # DETERMINAR INPUT:
        # Si tiene padre -> Output del padre (padre.gro)
        # Si no tiene padre -> system.gro (Salida de Topología)
        if parent_item:
            input_gro = f"{parent_item.text(0)}.gro"
        else:
            input_gro = "system.gro"
            
        storage_dir = os.path.join(self.current_project_path, "storage")
        
        if not os.path.exists(os.path.join(storage_dir, input_gro)):
            QMessageBox.warning(self, "Bloqueo", f"No se encuentra el input: {input_gro}\nEjecute el paso padre primero.")
            return
            
        mdp_file = f"{current_name}.mdp"
        if not os.path.exists(os.path.join(storage_dir, mdp_file)):
            QMessageBox.warning(self, "Error", "Guarde MDP primero.")
            return

        cmd = ["gmx", "grompp", "-f", mdp_file, "-c", input_gro, "-p", "topol.top", "-o", f"{current_name}.tpr", "-maxwarn", "2"]
        
        self.worker = CommandWorker(cmd, storage_dir)
        self.worker.log_signal.connect(lambda s: print(f"GMX: {s}"))
        self.worker.finished_signal.connect(self.on_grompp_finished)
        self.btn_grompp.setEnabled(False); self.worker.start()

    def on_grompp_finished(self, s, m):
        self.btn_grompp.setEnabled(True)
        if s: QMessageBox.information(self, "OK", "TPR Generado"); self.btn_mdrun.setEnabled(True)
        else: QMessageBox.critical(self, "Error", m)

    def run_mdrun(self):
        item = self.tree_steps.currentItem()
        name = item.text(0)
        
        # Calcular pasos para barra
        ns = self.spin_time.value(); dt = self.s_dt.value()
        self.total_steps_target = int((ns*1000)/dt) if dt > 0 and item.text(1) != 'minim' else 50000
        
        cmd = ["gmx", "mdrun", "-v", "-deffnm", name]
        self.worker = CommandWorker(cmd, os.path.join(self.current_project_path, "storage"))
        self.worker.log_signal.connect(self.parse_log)
        self.worker.finished_signal.connect(self.on_mdrun_finished)
        
        self.btn_grompp.setEnabled(False); self.btn_mdrun.setEnabled(False); self.btn_stop.setEnabled(True)
        item.setText(2, "Corriendo..."); item.setForeground(2, Qt.GlobalColor.blue)
        self.elapsed_seconds_counter = 0; self.timer.start(1000); self.worker.start()

    def stop_simulation(self):
        if self.worker: self.worker.stop_process()

    def on_mdrun_finished(self, s, m):
        self.timer.stop()
        item = self.tree_steps.currentItem()
        self.btn_grompp.setEnabled(True); self.btn_mdrun.setEnabled(True); self.btn_stop.setEnabled(False)
        item.setText(2, "Completado" if s else "Error")
        item.setForeground(2, Qt.GlobalColor.green if s else Qt.GlobalColor.red)
        if s: self.lbl_eta.setText("Finalizado"); QMessageBox.information(self, "Fin", "Terminó.")
        else: QMessageBox.warning(self, "Error", m)

    def parse_log(self, text):
        line = text.strip()
        if "finish time" in line.lower(): self.lbl_eta.setText(line.split(":",1)[1].strip())
        if "Rem:" in line: 
            try: self.lbl_eta.setText("Faltan: " + line.split("Rem:")[1].split("  ")[0])
            except: pass
    
    def update_elapsed_time(self):
        self.elapsed_seconds_counter += 1
        self.lbl_elapsed.setText("Transcurrido: " + str(datetime.timedelta(seconds=self.elapsed_seconds_counter)))