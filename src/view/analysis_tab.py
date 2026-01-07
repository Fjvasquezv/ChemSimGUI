import os
import subprocess
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QSplitter, QTabWidget, QSpinBox, 
    QRadioButton, QLineEdit, QButtonGroup, QStackedWidget, QCheckBox,
    QDialog, QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt
from src.model.analysis_parser import AnalysisParser

# Matplotlib
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# ==========================================================
# CLASE AUXILIAR: DIÁLOGO DE SELECCIÓN DE ÁTOMOS
# ==========================================================
class AtomSelectionDialog(QDialog):
    def __init__(self, structure_map, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Explorador de Estructura")
        self.resize(400, 500)
        self.selected_command = None 
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Despliegue los residuos y seleccione un átomo:"))
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Átomos Disponibles")
        layout.addWidget(self.tree)
        
        # Llenar el árbol
        for res_name, atoms in structure_map.items():
            # Nodo Padre: Residuo
            res_item = QTreeWidgetItem(self.tree)
            res_item.setText(0, f"Residuo: {res_name}")
            # Data oculta: comando para seleccionar todo el residuo
            res_item.setData(0, Qt.ItemDataRole.UserRole, f"r {res_name}") 
            
            # Nodos Hijos: Átomos individuales
            for atom in sorted(atoms):
                atom_item = QTreeWidgetItem(res_item)
                atom_item.setText(0, f"Átomo: {atom}")
                # Data oculta: comando para seleccionar el átomo
                atom_item.setData(0, Qt.ItemDataRole.UserRole, f"a {atom}") 
        
        self.tree.expandAll()
        
        btn_select = QPushButton("Crear Grupo con Selección")
        btn_select.clicked.connect(self.accept_selection)
        layout.addWidget(btn_select)
        
        self.setLayout(layout)

    def accept_selection(self):
        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Aviso", "Por favor seleccione un elemento del árbol.")
            return
        
        # Recuperar el comando oculto (ej "a OW")
        self.selected_command = item.data(0, Qt.ItemDataRole.UserRole)
        self.accept()


# ==========================================================
# CLASE PRINCIPAL: PESTAÑA DE ANÁLISIS
# ==========================================================
class AnalysisTab(QWidget):
    def __init__(self):
        super().__init__()
        self.parser = AnalysisParser()
        self.project_mgr = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- 1. SELECCIÓN DE SIMULACIÓN ---
        group_sel = QGroupBox("1. Selección de Datos")
        hbox_sel = QHBoxLayout()
        
        self.combo_sims = QComboBox()
        self.combo_sims.currentIndexChanged.connect(self.on_sim_changed)
        
        hbox_sel.addWidget(QLabel("Simulación a analizar:"))
        hbox_sel.addWidget(self.combo_sims)
        hbox_sel.addStretch()
        
        group_sel.setLayout(hbox_sel)
        layout.addWidget(group_sel)
        
        # --- 2. PESTAÑAS INTERNAS DE ANÁLISIS ---
        self.tabs_analysis = QTabWidget()
        
        # Tab A: Termodinámica
        self.tab_thermo = QWidget()
        self.init_thermo_ui()
        self.tabs_analysis.addTab(self.tab_thermo, "Termodinámica")
        
        # Tab B: Estructura (RDF)
        self.tab_struct = QWidget()
        self.init_struct_ui()
        self.tabs_analysis.addTab(self.tab_struct, "Estructura (RDF)")
        
        layout.addWidget(self.tabs_analysis)
        self.setLayout(layout)

    # ----------------------------------------------------------
    # UI PARTE A: TERMODINÁMICA
    # ----------------------------------------------------------
    def init_thermo_ui(self):
        layout = QVBoxLayout()
        
        # Botones de propiedades rápidas
        hbox_ctrl = QHBoxLayout()
        
        btn_temp = QPushButton("🌡️ Temperatura")
        btn_temp.clicked.connect(lambda: self.analyze_property("Temperature"))
        
        btn_press = QPushButton("⚖️ Presión")
        btn_press.clicked.connect(lambda: self.analyze_property("Pressure"))
        
        btn_dens = QPushButton("💧 Densidad")
        btn_dens.clicked.connect(lambda: self.analyze_property("Density"))
        
        btn_pot = QPushButton("⚡ Potencial")
        btn_pot.clicked.connect(lambda: self.analyze_property("Potential"))
        
        hbox_ctrl.addWidget(btn_temp)
        hbox_ctrl.addWidget(btn_press)
        hbox_ctrl.addWidget(btn_dens)
        hbox_ctrl.addWidget(btn_pot)
        
        layout.addLayout(hbox_ctrl)
        
        # Splitter para Tabla y Gráfico
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Tabla de Estadísticas
        self.table_stats = QTableWidget()
        self.table_stats.setColumnCount(3)
        self.table_stats.setHorizontalHeaderLabels(["Propiedad", "Promedio", "Desv. Std"])
        self.table_stats.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_stats.setMaximumHeight(80)
        splitter.addWidget(self.table_stats)
        
        # Gráfico
        self.figure_thermo = Figure()
        self.canvas_thermo = FigureCanvas(self.figure_thermo)
        splitter.addWidget(self.canvas_thermo)
        
        layout.addWidget(splitter)
        self.tab_thermo.setLayout(layout)

    # ----------------------------------------------------------
    # UI PARTE B: ESTRUCTURA (RDF y PBC)
    # ----------------------------------------------------------
    def init_struct_ui(self):
        layout = QVBoxLayout()
        
        # --- SUB-SECCIÓN: PBC ---
        group_pbc = QGroupBox("Corrección de Trayectoria (PBC)")
        layout_pbc = QVBoxLayout()
        
        hbox_pbc = QHBoxLayout()
        hbox_pbc.addWidget(QLabel("Centrar Grupo ID:"))
        self.spin_center = QSpinBox()
        self.spin_center.setValue(1)
        hbox_pbc.addWidget(self.spin_center)
        
        hbox_pbc.addWidget(QLabel("Output ID:"))
        self.spin_output = QSpinBox()
        self.spin_output.setValue(0)
        hbox_pbc.addWidget(self.spin_output)
        
        self.btn_trjconv = QPushButton("🛠️ Corregir (gmx trjconv)")
        self.btn_trjconv.clicked.connect(self.run_trjconv)
        hbox_pbc.addWidget(self.btn_trjconv)
        
        layout_pbc.addLayout(hbox_pbc)
        group_pbc.setLayout(layout_pbc)
        layout.addWidget(group_pbc)
        
        # --- SUB-SECCIÓN: RDF ---
        group_rdf = QGroupBox("Función de Distribución Radial (RDF)")
        layout_rdf = QVBoxLayout()
        
        # Selector de Motor
        hbox_engine = QHBoxLayout()
        hbox_engine.addWidget(QLabel("Motor de Cálculo:"))
        self.rb_gmx = QRadioButton("GROMACS (Avanzado)")
        self.rb_gmx.setChecked(True)
        self.rb_travis = QRadioButton("TRAVIS (Por Nombre)")
        
        self.bg_engine = QButtonGroup()
        self.bg_engine.addButton(self.rb_gmx)
        self.bg_engine.addButton(self.rb_travis)
        self.rb_gmx.toggled.connect(self.update_rdf_inputs)
        
        hbox_engine.addWidget(self.rb_gmx)
        hbox_engine.addWidget(self.rb_travis)
        hbox_engine.addStretch()
        layout_rdf.addLayout(hbox_engine)
        
        # Stack para cambiar inputs dinámicamente
        self.stack_rdf = QStackedWidget()
        
        # PANEL 1: GROMACS (Combos y Explorador)
        w_gmx = QWidget()
        layout_gmx = QVBoxLayout()
        
        hbox_gmx_sel = QHBoxLayout()
        self.combo_ref = QComboBox()
        self.combo_sel = QComboBox()
        hbox_gmx_sel.addWidget(QLabel("Referencia:"))
        hbox_gmx_sel.addWidget(self.combo_ref)
        hbox_gmx_sel.addWidget(QLabel("Selección:"))
        hbox_gmx_sel.addWidget(self.combo_sel)
        layout_gmx.addLayout(hbox_gmx_sel)
        
        hbox_gmx_tools = QHBoxLayout()
        btn_explore = QPushButton("🔍 Explorar Átomos y Crear Grupo")
        btn_explore.clicked.connect(self.open_atom_explorer)
        
        self.chk_com = QCheckBox("Usar Centros de Masa")
        
        hbox_gmx_tools.addWidget(btn_explore)
        hbox_gmx_tools.addWidget(self.chk_com)
        layout_gmx.addLayout(hbox_gmx_tools)
        
        w_gmx.setLayout(layout_gmx)
        self.stack_rdf.addWidget(w_gmx)
        
        # PANEL 2: TRAVIS (Inputs de Texto)
        w_travis = QWidget()
        layout_travis = QHBoxLayout()
        self.txt_mol_ref = QLineEdit()
        self.txt_mol_ref.setPlaceholderText("Nombre Mol 1 (ej: CBD)")
        self.txt_mol_sel = QLineEdit()
        self.txt_mol_sel.setPlaceholderText("Nombre Mol 2 (ej: SOL)")
        
        layout_travis.addWidget(QLabel("Molécula 1:"))
        layout_travis.addWidget(self.txt_mol_ref)
        layout_travis.addWidget(QLabel("Molécula 2:"))
        layout_travis.addWidget(self.txt_mol_sel)
        
        w_travis.setLayout(layout_travis)
        self.stack_rdf.addWidget(w_travis)
        
        layout_rdf.addWidget(self.stack_rdf)
        
        # Botón Calcular
        self.btn_rdf = QPushButton("📊 Calcular RDF")
        self.btn_rdf.clicked.connect(self.run_rdf)
        layout_rdf.addWidget(self.btn_rdf)
        
        group_rdf.setLayout(layout_rdf)
        layout.addWidget(group_rdf)
        
        # Gráfico RDF
        self.figure_rdf = Figure()
        self.canvas_rdf = FigureCanvas(self.figure_rdf)
        layout.addWidget(self.canvas_rdf)
        
        self.tab_struct.setLayout(layout)

    # ----------------------------------------------------------
    # LÓGICA GENERAL
    # ----------------------------------------------------------
    
    def update_project_data(self, project_mgr):
        """Carga la lista de simulaciones disponibles"""
        self.project_mgr = project_mgr
        if not project_mgr or not project_mgr.current_project_path:
            return
            
        storage_dir = os.path.join(project_mgr.current_project_path, "storage")
        
        self.combo_sims.clear()
        
        if os.path.exists(storage_dir):
            files = os.listdir(storage_dir)
            # Buscamos TPRs (definen una simulación válida)
            tpr_files = [f for f in files if f.endswith(".tpr")]
            
            for f in sorted(tpr_files):
                name = os.path.splitext(f)[0]
                self.combo_sims.addItem(name)

    def on_sim_changed(self):
        """Limpiar gráficas y recargar grupos si es necesario"""
        self.figure_thermo.clear()
        self.canvas_thermo.draw()
        self.figure_rdf.clear()
        self.canvas_rdf.draw()
        self.table_stats.setRowCount(0)
        
        if self.rb_gmx.isChecked():
            self.load_gromacs_groups()

    # ----------------------------------------------------------
    # LÓGICA TERMODINÁMICA
    # ----------------------------------------------------------
    
    def analyze_property(self, prop_name):
        sim_name = self.combo_sims.currentText()
        if not sim_name: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        edr_file = os.path.join(d, f"{sim_name}.edr")
        xvg_file = os.path.join(d, f"{sim_name}_{prop_name}.xvg")
        
        # Ejecutar gmx energy
        success, msg = self.parser.run_gmx_energy(edr_file, xvg_file, [prop_name])
        
        if not success:
            QMessageBox.warning(self, "Error GROMACS", msg)
            return
            
        # Leer y graficar
        labels, x, y_list = self.parser.get_data_from_file(xvg_file)
        
        if y_list:
            y = y_list[0]
            
            # Tabla
            self.table_stats.setRowCount(1)
            self.table_stats.setItem(0, 0, QTableWidgetItem(prop_name))
            self.table_stats.setItem(0, 1, QTableWidgetItem(f"{np.mean(y):.4f}"))
            self.table_stats.setItem(0, 2, QTableWidgetItem(f"{np.std(y):.4f}"))
            
            # Gráfico
            self.figure_thermo.clear()
            ax = self.figure_thermo.add_subplot(111)
            ax.plot(x, y, label=prop_name, color='blue')
            ax.set_title(f"{prop_name} - {sim_name}")
            ax.set_xlabel(labels[0])
            ax.set_ylabel(labels[1])
            ax.legend()
            ax.grid(True, alpha=0.3)
            self.canvas_thermo.draw()

    # ----------------------------------------------------------
    # LÓGICA ESTRUCTURAL Y GRUPOS
    # ----------------------------------------------------------

    def run_trjconv(self):
        sim_name = self.combo_sims.currentText()
        if not sim_name: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim_name}.tpr")
        xtc = os.path.join(d, f"{sim_name}.xtc")
        
        if not os.path.exists(xtc):
            QMessageBox.warning(self, "Error", "No existe archivo .xtc")
            return
            
        clean_xtc = os.path.join(d, f"{sim_name}_clean.xtc")
        
        success, msg = self.parser.run_trjconv(
            tpr, xtc, clean_xtc, 
            self.spin_center.value(), self.spin_output.value()
        )
        
        if success:
            QMessageBox.information(self, "Éxito", "Trayectoria corregida.")
        else:
            QMessageBox.critical(self, "Error", msg)

    def update_rdf_inputs(self):
        if self.rb_gmx.isChecked():
            self.stack_rdf.setCurrentIndex(0)
            self.load_gromacs_groups()
        else:
            self.stack_rdf.setCurrentIndex(1)

    def load_gromacs_groups(self):
        """Carga los grupos del index.ndx en los ComboBox"""
        sim_name = self.combo_sims.currentText()
        if not sim_name or not self.project_mgr: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim_name}.tpr")
        
        groups = self.parser.get_gromacs_groups(tpr, d)
        
        self.combo_ref.clear()
        self.combo_sel.clear()
        
        for name, idx in groups.items():
            self.combo_ref.addItem(f"{name} ({idx})", idx)
            self.combo_sel.addItem(f"{name} ({idx})", idx)

    def open_atom_explorer(self):
        """Abre el diálogo visual para crear grupos"""
        sim_name = self.combo_sims.currentText()
        if not sim_name: return
        
        # Necesitamos el .gro para ver nombres
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        gro_file = os.path.join(d, "system.gro")
        
        if not os.path.exists(gro_file):
            QMessageBox.warning(self, "Error", "Falta system.gro para leer estructura.")
            return
            
        structure_map = self.parser.scan_structure_atoms(gro_file)
        
        dlg = AtomSelectionDialog(structure_map, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            command = dlg.selected_command
            if command:
                # Crear grupo
                tpr = os.path.join(d, f"{sim_name}.tpr")
                success, msg = self.parser.add_custom_group(tpr, d, command)
                
                if success:
                    QMessageBox.information(self, "Éxito", "Grupo creado.")
                    self.load_gromacs_groups()
                else:
                    QMessageBox.critical(self, "Error", msg)

    def run_rdf(self):
        sim_name = self.combo_sims.currentText()
        if not sim_name: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim_name}.tpr")
        xtc = os.path.join(d, f"{sim_name}_clean.xtc")
        if not os.path.exists(xtc): xtc = os.path.join(d, f"{sim_name}.xtc")
        
        success = False
        msg = ""
        out_file = ""
        
        if self.rb_gmx.isChecked():
            # RDF GROMACS
            out_file = os.path.join(d, f"{sim_name}_rdf_gmx.xvg")
            ref = self.combo_ref.currentData()
            sel = self.combo_sel.currentData()
            if ref is None: return
            
            success, msg = self.parser.run_gmx_rdf(
                tpr, xtc, out_file, ref, sel, d, self.chk_com.isChecked()
            )
        else:
            # RDF TRAVIS
            out_file = os.path.join(d, f"{sim_name}_rdf_travis.csv")
            struct = os.path.join(d, "system.gro")
            m1 = self.txt_mol_ref.text()
            m2 = self.txt_mol_sel.text()
            
            success, msg = self.parser.run_travis_rdf(struct, xtc, out_file, m1, m2)
            
        if success:
            labels, x, y_list = self.parser.get_data_from_file(out_file)
            if y_list:
                self.figure_rdf.clear()
                ax = self.figure_rdf.add_subplot(111)
                ax.plot(x, y_list[0], color='red', label="RDF")
                ax.set_title(f"RDF - {sim_name}")
                ax.set_xlabel(labels[0])
                ax.set_ylabel("g(r)")
                ax.grid(True, alpha=0.3)
                self.canvas_rdf.draw()
        else:
            QMessageBox.critical(self, "Error", msg)