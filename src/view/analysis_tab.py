import os
import subprocess
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QGroupBox, QTableWidget, QTableWidgetItem, 
    QHeaderView, QMessageBox, QSplitter, QTabWidget, QSpinBox, 
    QRadioButton, QLineEdit, QButtonGroup, QStackedWidget, QCheckBox,
    QDialog, QTreeWidget, QTreeWidgetItem, QApplication, QScrollArea,
    QDoubleSpinBox, QColorDialog, QFormLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor
from src.model.analysis_parser import AnalysisParser
from src.model.molecule_graph import MoleculeGraphGenerator

# Matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

# ==========================================================
# WORKER: HILO DE EJECUCIÓN
# ==========================================================
class AnalysisWorker(QThread):
    finished_signal = pyqtSignal(bool, str) # (Success, Message)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            # Ejecuta la función pasando los argumentos
            success, msg = self.func(*self.args, **self.kwargs)
            self.finished_signal.emit(success, msg)
        except Exception as e:
            self.finished_signal.emit(False, str(e))

# ==========================================================
# DIÁLOGO DE SELECCIÓN CON VISUALIZACIÓN
# ==========================================================
class AtomSelectionDialog(QDialog):
    def __init__(self, structure_map, gro_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Explorador Visual de Estructura")
        self.resize(1100, 700)
        self.selected_command = None
        self.gro_path = gro_path
        
        # Generador de gráficos moleculares
        self.graph_gen = MoleculeGraphGenerator()
        
        # Directorio de cache para imágenes generadas
        self.image_cache_dir = os.path.join(os.path.dirname(gro_path), "mol_images")
        os.makedirs(self.image_cache_dir, exist_ok=True)
        
        # Layout Principal
        layout = QVBoxLayout()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # --- PANEL IZQUIERDO (ÁRBOL) ---
        widget_left = QWidget()
        vbox_left = QVBoxLayout()
        vbox_left.addWidget(QLabel("1. Seleccione Residuo/Átomo:"))
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Sistema")
        self.tree.itemClicked.connect(self.on_item_clicked)
        vbox_left.addWidget(self.tree)
        
        widget_left.setLayout(vbox_left)
        
        # Llenar el árbol con los datos del GRO
        for res_name, atoms in structure_map.items():
            res_item = QTreeWidgetItem(self.tree)
            res_item.setText(0, f"Residuo: {res_name}")
            res_item.setData(0, Qt.ItemDataRole.UserRole, f"r {res_name}")
            res_item.setData(0, Qt.ItemDataRole.UserRole + 1, res_name) 
            
            for atom in sorted(atoms):
                atom_item = QTreeWidgetItem(res_item)
                atom_item.setText(0, f"{atom}")
                atom_item.setData(0, Qt.ItemDataRole.UserRole, f"a {atom}")
                atom_item.setData(0, Qt.ItemDataRole.UserRole + 1, res_name)
        
        # --- PANEL DERECHO (VISUALIZADOR) ---
        widget_right = QWidget()
        vbox_right = QVBoxLayout()
        vbox_right.addWidget(QLabel("2. Diagrama Estructural (Ayuda Visual):"))
        
        self.scroll_area = QScrollArea()
        self.lbl_image = QLabel("Seleccione un residuo para ver su estructura.")
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.lbl_image)
        self.scroll_area.setWidgetResizable(True)
        
        vbox_right.addWidget(self.scroll_area)
        widget_right.setLayout(vbox_right)
        
        # Configurar Splitter
        splitter.addWidget(widget_left)
        splitter.addWidget(widget_right)
        splitter.setStretchFactor(1, 2)
        
        layout.addWidget(splitter)
        
        # Botón Confirmar
        btn_select = QPushButton("Confirmar Selección")
        btn_select.clicked.connect(self.accept_selection)
        btn_select.setStyleSheet("font-weight: bold; padding: 10px; background-color: #007bff; color: white;")
        layout.addWidget(btn_select)
        
        self.setLayout(layout)

    def on_item_clicked(self, item, col):
        """Genera imagen con Graphviz al hacer clic"""
        res_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not res_name:
            return
        
        img_path = os.path.join(self.image_cache_dir, f"{res_name}.png")
        
        if not os.path.exists(img_path):
            self.lbl_image.setText(f"Generando diagrama para {res_name}...")
            self.lbl_image.repaint()
            QApplication.processEvents()
            
            success, result = self.graph_gen.generate_image(self.gro_path, res_name, img_path)
            
            if not success:
                self.lbl_image.setText(f"Error generando imagen:\n{result}")
                return
                
        pixmap = QPixmap(img_path)
        if not pixmap.isNull():
            if pixmap.width() > 600:
                pixmap = pixmap.scaledToWidth(600, Qt.TransformationMode.SmoothTransformation)
            self.lbl_image.setPixmap(pixmap)
        else:
            self.lbl_image.setText("Error cargando imagen.")

    def accept_selection(self):
        item = self.tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Aviso", "Seleccione un elemento.")
            return
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
        self.worker = None
        
        # ALMACÉN DE DATOS PARA GRAFICACIÓN AVANZADA
        # Estructura: { 'id_unico': {'label': 'Temp (Sim1)', 'x': [...], 'y': [...]} }
        self.data_store = {} 
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # --- 1. SELECCIÓN DE SIMULACIÓN ---
        group_sel = QGroupBox("1. Origen de Datos")
        hbox_sel = QHBoxLayout()
        
        self.combo_sims = QComboBox()
        self.combo_sims.currentIndexChanged.connect(self.on_sim_changed)
        
        hbox_sel.addWidget(QLabel("Simulación Actual:"))
        hbox_sel.addWidget(self.combo_sims)
        hbox_sel.addStretch()
        
        group_sel.setLayout(hbox_sel)
        layout.addWidget(group_sel)
        
        # --- 2. PESTAÑAS PRINCIPALES ---
        self.tabs = QTabWidget()
        
        # Tab A: Cálculo Termodinámico
        self.tab_calc_thermo = QWidget()
        self.init_calc_thermo()
        self.tabs.addTab(self.tab_calc_thermo, "Calc. Termodinámica")
        
        # Tab B: Cálculo Estructural (RDF)
        self.tab_calc_struct = QWidget()
        self.init_calc_struct()
        self.tabs.addTab(self.tab_calc_struct, "Calc. Estructura (RDF)")
        
        # Tab C: Visualización Avanzada (Paper)
        self.tab_viz = QWidget()
        self.init_viz_advanced()
        self.tabs.addTab(self.tab_viz, "Visualización Avanzada (Paper)")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)

    # ------------------------------------------------------
    # UI: CÁLCULO TERMODINÁMICA
    # ------------------------------------------------------
    def init_calc_thermo(self):
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Extraer propiedades del archivo de energía (.edr) y añadirlas al graficador."))
        
        hbox_btns = QHBoxLayout()
        for prop in ["Temperature", "Pressure", "Density", "Potential"]:
            btn = QPushButton(prop)
            btn.clicked.connect(lambda ch, pr=prop: self.run_energy(pr))
            hbox_btns.addWidget(btn)
        
        layout.addLayout(hbox_btns)
        
        self.lbl_thermo_status = QLabel("Estado: Listo para calcular")
        self.lbl_thermo_status.setStyleSheet("color: gray;")
        layout.addWidget(self.lbl_thermo_status)
        
        layout.addStretch()
        self.tab_calc_thermo.setLayout(layout)

    # ------------------------------------------------------
    # UI: CÁLCULO ESTRUCTURA
    # ------------------------------------------------------
    def init_calc_struct(self):
        layout = QVBoxLayout()
        
        # --- SUBSECCIÓN: PBC ---
        group_pbc = QGroupBox("Corrección de Trayectoria (PBC)")
        vbox_pbc = QVBoxLayout()
        hbox_pbc = QHBoxLayout()
        
        self.sb_center = QSpinBox()
        self.sb_center.setValue(1)
        self.sb_out = QSpinBox()
        self.sb_out.setValue(0)
        
        hbox_pbc.addWidget(QLabel("Centrar ID:"))
        hbox_pbc.addWidget(self.sb_center)
        hbox_pbc.addWidget(QLabel("Output ID:"))
        hbox_pbc.addWidget(self.sb_out)
        
        btn_trj = QPushButton("Correr trjconv")
        btn_trj.clicked.connect(self.run_trjconv)
        hbox_pbc.addWidget(btn_trj)
        
        vbox_pbc.addLayout(hbox_pbc)
        group_pbc.setLayout(vbox_pbc)
        layout.addWidget(group_pbc)
        
        # --- SUBSECCIÓN: RDF ---
        group_rdf = QGroupBox("Cálculo RDF")
        vbox_rdf = QVBoxLayout()
        
        # Configuración General
        hbox_cfg = QHBoxLayout()
        self.rb_gmx = QRadioButton("GROMACS")
        self.rb_gmx.setChecked(True)
        self.rb_travis = QRadioButton("TRAVIS")
        
        bg = QButtonGroup(self)
        bg.addButton(self.rb_gmx)
        bg.addButton(self.rb_travis)
        self.rb_gmx.toggled.connect(self.update_rdf_ui)
        
        # Configuración de BIN
        self.sb_bin = QDoubleSpinBox()
        self.sb_bin.setRange(0.001, 1.0)
        self.sb_bin.setSingleStep(0.001)
        self.sb_bin.setValue(0.002)
        self.sb_bin.setDecimals(4)
        self.sb_bin.setSuffix(" nm")
        
        hbox_cfg.addWidget(QLabel("Motor:"))
        hbox_cfg.addWidget(self.rb_gmx)
        hbox_cfg.addWidget(self.rb_travis)
        hbox_cfg.addSpacing(20)
        hbox_cfg.addWidget(QLabel("Resolución (Bin):"))
        hbox_cfg.addWidget(self.sb_bin)
        
        vbox_rdf.addLayout(hbox_cfg)
        
        # Stack para inputs variables
        self.stack_rdf = QStackedWidget()
        
        # PÁGINA GROMACS
        w_gmx = QWidget()
        v_gmx = QVBoxLayout()
        h_gmx_sel = QHBoxLayout()
        
        self.cb_ref = QComboBox()
        self.cb_sel = QComboBox()
        h_gmx_sel.addWidget(QLabel("Ref:"))
        h_gmx_sel.addWidget(self.cb_ref)
        h_gmx_sel.addWidget(QLabel("Sel:"))
        h_gmx_sel.addWidget(self.cb_sel)
        
        h_gmx_tools = QHBoxLayout()
        btn_exp = QPushButton("🔍 Explorar / Crear Grupos")
        btn_exp.clicked.connect(self.open_explorer)
        self.chk_com = QCheckBox("Usar Centros de Masa")
        
        h_gmx_tools.addWidget(btn_exp)
        h_gmx_tools.addWidget(self.chk_com)
        
        v_gmx.addLayout(h_gmx_sel)
        v_gmx.addLayout(h_gmx_tools)
        w_gmx.setLayout(v_gmx)
        self.stack_rdf.addWidget(w_gmx)
        
        # PÁGINA TRAVIS
        w_travis = QWidget()
        h_travis = QHBoxLayout()
        self.tx_m1 = QLineEdit()
        self.tx_m1.setPlaceholderText("Mol 1 (ej. CBD)")
        self.tx_m2 = QLineEdit()
        self.tx_m2.setPlaceholderText("Mol 2 (ej. SOL)")
        
        h_travis.addWidget(QLabel("Mol 1:"))
        h_travis.addWidget(self.tx_m1)
        h_travis.addWidget(QLabel("Mol 2:"))
        h_travis.addWidget(self.tx_m2)
        
        w_travis.setLayout(h_travis)
        self.stack_rdf.addWidget(w_travis)
        
        vbox_rdf.addWidget(self.stack_rdf)
        
        # Botón Calcular
        btn_calc_rdf = QPushButton("Calcular y Añadir a Gráficas")
        btn_calc_rdf.clicked.connect(self.run_rdf)
        btn_calc_rdf.setStyleSheet("font-weight: bold; color: green; padding: 5px;")
        vbox_rdf.addWidget(btn_calc_rdf)
        
        group_rdf.setLayout(vbox_rdf)
        layout.addWidget(group_rdf)
        
        layout.addStretch()
        self.tab_calc_struct.setLayout(layout)

    # ------------------------------------------------------
    # UI: VISUALIZACIÓN AVANZADA (MULTIPANEL)
    # ------------------------------------------------------
    def init_viz_advanced(self):
        layout = QVBoxLayout()
        
        # 1. Configuración Gráfica
        group_cfg = QGroupBox("Configuración de Figura")
        hbox_cfg = QHBoxLayout()
        
        self.combo_layout = QComboBox()
        self.combo_layout.addItems(["1 Gráfico (Simple)", "2 Gráficos (1x2)", "4 Gráficos (2x2)"])
        self.combo_layout.currentIndexChanged.connect(self.update_plot_layout)
        
        self.sb_fontsize = QSpinBox()
        self.sb_fontsize.setRange(8, 30)
        self.sb_fontsize.setValue(12)
        
        self.sb_linewidth = QDoubleSpinBox()
        self.sb_linewidth.setRange(0.5, 5.0)
        self.sb_linewidth.setValue(1.5)
        
        btn_update_plot = QPushButton("🔄 Actualizar Gráfico")
        btn_update_plot.clicked.connect(self.update_plot_layout)
        
        hbox_cfg.addWidget(QLabel("Disposición:"))
        hbox_cfg.addWidget(self.combo_layout)
        hbox_cfg.addWidget(QLabel("Tamaño Fuente:"))
        hbox_cfg.addWidget(self.sb_fontsize)
        hbox_cfg.addWidget(QLabel("Grosor Línea:"))
        hbox_cfg.addWidget(self.sb_linewidth)
        hbox_cfg.addWidget(btn_update_plot)
        
        group_cfg.setLayout(hbox_cfg)
        layout.addWidget(group_cfg)
        
        # 2. Matriz de Asignación (Tabla)
        self.table_map = QTableWidget()
        self.table_map.setColumnCount(5)
        self.table_map.setHorizontalHeaderLabels(["Serie de Datos", "Plot 1", "Plot 2", "Plot 3", "Plot 4"])
        self.table_map.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_map.setMaximumHeight(150)
        layout.addWidget(self.table_map)
        
        # 3. Canvas Matplotlib
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)
        
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        
        self.tab_viz.setLayout(layout)

    # ==========================================================
    # GESTIÓN DE DATOS (DATA STORE)
    # ==========================================================
    
    def add_data_to_store(self, label, x, y):
        """Guarda un set de datos calculado y lo añade a la tabla de visualización"""
        # Crear ID único
        data_id = f"{len(self.data_store)}_{label}"
        
        # Guardar en memoria
        self.data_store[data_id] = {
            'label': label,
            'x': x,
            'y': y
        }
        
        # Añadir fila a la tabla
        row = self.table_map.rowCount()
        self.table_map.insertRow(row)
        
        # Nombre (Columna 0)
        item_name = QTableWidgetItem(label)
        # Guardamos el ID en el item para recuperarlo luego
        item_name.setData(Qt.ItemDataRole.UserRole, data_id)
        self.table_map.setItem(row, 0, item_name)
        
        # Checkboxes (Columnas 1-4)
        for col in range(1, 5):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Unchecked)
            
            # Por defecto, marcar en Plot 1
            if col == 1:
                chk.setCheckState(Qt.CheckState.Checked)
                
            self.table_map.setItem(row, col, chk)
            
        # Cambiar automáticamente a la pestaña de visualización
        self.tabs.setCurrentIndex(2)
        self.update_plot_layout()

    def update_project_data(self, mgr):
        self.project_mgr = mgr
        if not mgr or not mgr.current_project_path:
            return
            
        d = os.path.join(mgr.current_project_path, "storage")
        self.combo_sims.clear()
        
        if os.path.exists(d):
            files = os.listdir(d)
            tpr_files = [f for f in sorted(files) if f.endswith(".tpr")]
            for f in tpr_files:
                self.combo_sims.addItem(os.path.splitext(f)[0])

    def on_sim_changed(self):
        if self.rb_gmx.isChecked():
            self.load_gmx_groups()

    def update_rdf_ui(self):
        if self.rb_gmx.isChecked():
            self.stack_rdf.setCurrentIndex(0)
            self.load_gmx_groups()
        else:
            self.stack_rdf.setCurrentIndex(1)

    def load_gmx_groups(self):
        sim = self.combo_sims.currentText()
        if not sim: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim}.tpr")
        
        groups = self.parser.get_gromacs_groups(tpr, d)
        
        self.cb_ref.clear()
        self.cb_sel.clear()
        
        for n, i in groups.items():
            txt = f"{n} ({i})"
            self.cb_ref.addItem(txt, i)
            self.cb_sel.addItem(txt, i)

    def set_busy(self, busy):
        self.setEnabled(not busy)

    # ==========================================================
    # EJECUCIÓN DE CÁLCULOS
    # ==========================================================

    # --- 1. ENERGÍA ---
    def run_energy(self, prop):
        sim = self.combo_sims.currentText()
        if not sim: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        edr = os.path.join(d, f"{sim}.edr")
        out = os.path.join(d, f"{sim}_{prop}.xvg")
        
        self.set_busy(True)
        self.worker = AnalysisWorker(self.parser.run_gmx_energy, edr, out, [prop])
        self.worker.finished_signal.connect(lambda s, m: self.finish_calc(s, m, out, f"{prop} ({sim})"))
        self.worker.start()

    # --- 2. TRJCONV ---
    def run_trjconv(self):
        sim = self.combo_sims.currentText()
        if not sim: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim}.tpr")
        xtc = os.path.join(d, f"{sim}.xtc")
        out = os.path.join(d, f"{sim}_clean.xtc")
        
        if not os.path.exists(xtc):
            QMessageBox.warning(self, "Error", "No existe .xtc")
            return
        
        self.set_busy(True)
        self.worker = AnalysisWorker(
            self.parser.run_trjconv, tpr, xtc, out, 
            self.sb_center.value(), self.sb_out.value()
        )
        self.worker.finished_signal.connect(lambda s, m: (self.set_busy(False), QMessageBox.information(self, "OK", "Listo") if s else QMessageBox.critical(self, "Error", m)))
        self.worker.start()

    # --- 3. RDF ---
    def run_rdf(self):
        sim = self.combo_sims.currentText()
        if not sim: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        tpr = os.path.join(d, f"{sim}.tpr")
        xtc = os.path.join(d, f"{sim}_clean.xtc")
        if not os.path.exists(xtc):
            xtc = os.path.join(d, f"{sim}.xtc")
        
        self.set_busy(True)
        
        if self.rb_gmx.isChecked():
            # GROMACS
            out = os.path.join(d, f"{sim}_rdf_gmx.xvg")
            ref = self.cb_ref.currentData()
            sel = self.cb_sel.currentData()
            
            if ref is None: 
                self.set_busy(False); return
            
            self.worker = AnalysisWorker(
                self.parser.run_gmx_rdf, tpr, xtc, out, ref, sel, d, 
                self.chk_com.isChecked(), self.sb_bin.value()
            )
            label_base = f"RDF {self.cb_ref.currentText().split('(')[0]}-{self.cb_sel.currentText().split('(')[0]}"
            
        else:
            # TRAVIS
            out = os.path.join(d, f"{sim}_rdf_travis.csv")
            st = os.path.join(d, "system.gro")
            
            self.worker = AnalysisWorker(
                self.parser.run_travis_rdf, st, xtc, out, 
                self.tx_m1.text(), self.tx_m2.text()
            )
            label_base = f"RDF {self.tx_m1.text()}-{self.tx_m2.text()}"
        
        full_label = f"{label_base} ({sim})"
        self.worker.finished_signal.connect(lambda s, m: self.finish_calc(s, m, out, full_label))
        self.worker.start()

    def finish_calc(self, success, msg, out_file, label):
        self.set_busy(False)
        if not success:
            QMessageBox.critical(self, "Error", msg)
            return
        
        # Leer datos y añadir a Store
        lbl, x, y_list = self.parser.get_data_from_file(out_file)
        
        if y_list:
            self.add_data_to_store(label, x, y_list[0])
        else:
            QMessageBox.warning(self, "Aviso", "El archivo de salida está vacío o tiene formato incorrecto.")

    def open_explorer(self):
        sim = self.combo_sims.currentText()
        if not sim: return
        
        d = os.path.join(self.project_mgr.current_project_path, "storage")
        gro = os.path.join(d, "system.gro")
        
        if not os.path.exists(gro):
            QMessageBox.warning(self, "Error", "Falta system.gro")
            return
        
        struct = self.parser.scan_structure_atoms(gro)
        dlg = AtomSelectionDialog(struct, gro, self)
        
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_command:
            tpr = os.path.join(d, f"{sim}.tpr")
            
            self.set_busy(True)
            self.worker = AnalysisWorker(
                self.parser.add_custom_group, tpr, d, dlg.selected_command
            )
            self.worker.finished_signal.connect(lambda s, m: (self.set_busy(False), self.load_gmx_groups() if s else QMessageBox.critical(self, "Error", m)))
            self.worker.start()

    # ==========================================================
    # LÓGICA DE GRAFICACIÓN AVANZADA
    # ==========================================================
    def update_plot_layout(self):
        """Redibuja los gráficos según la configuración de la tabla"""
        self.figure.clear()
        
        # Configurar estilo global
        font_size = self.sb_fontsize.value()
        line_width = self.sb_linewidth.value()
        plt.rcParams.update({'font.size': font_size, 'lines.linewidth': line_width})
        
        layout_mode = self.combo_layout.currentIndex() # 0=1, 1=2, 2=4
        axes = []
        
        # Crear subplots
        if layout_mode == 0:
            axes.append(self.figure.add_subplot(111))
        elif layout_mode == 1:
            axes.append(self.figure.add_subplot(121))
            axes.append(self.figure.add_subplot(122))
        elif layout_mode == 2:
            axes.append(self.figure.add_subplot(221))
            axes.append(self.figure.add_subplot(222))
            axes.append(self.figure.add_subplot(223))
            axes.append(self.figure.add_subplot(224))
            
        # Recorrer la tabla para ver qué dato va en qué plot
        row_count = self.table_map.rowCount()
        
        for r in range(row_count):
            # Recuperar ID del dato
            item_name = self.table_map.item(r, 0)
            data_id = item_name.data(Qt.ItemDataRole.UserRole)
            
            data = self.data_store.get(data_id)
            if not data: continue
            
            # Revisar columnas de checkboxes (Col 1 a 4)
            for c in range(1, 5):
                # Si el gráfico no existe en este layout, saltar
                plot_idx = c - 1
                if plot_idx >= len(axes): break
                
                item_chk = self.table_map.item(r, c)
                if item_chk.checkState() == Qt.CheckState.Checked:
                    ax = axes[plot_idx]
                    ax.plot(data['x'], data['y'], label=data['label'])
                    
        # Decorar ejes
        for i, ax in enumerate(axes):
            ax.grid(True, linestyle='--', alpha=0.6)
            ax.legend(fontsize=font_size-2)
            ax.set_title(f"Gráfico {i+1}", fontweight='bold')
            # Etiquetas genéricas (podrían mejorarse guardando unidades en data_store)
            if i >= len(axes)-2: ax.set_xlabel("X Axis") # Solo abajo
            ax.set_ylabel("Y Axis")

        self.figure.tight_layout()
        self.canvas.draw()