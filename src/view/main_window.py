import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFileDialog, QMessageBox, 
                             QTabWidget, QFrame)
from PyQt6.QtCore import Qt
from src.model.project_manager import ProjectManager

# --- IMPORTACIÓN DE PESTAÑAS (MÓDULOS) ---
from src.view.setup_tab import SetupTab 
from src.view.topology_tab import TopologyTab
from src.view.simulation_tab import SimulationTab 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ChemSimGUI - Gestor de Tesis")
        self.setGeometry(100, 100, 950, 700)
        
        # Lógica del Proyecto
        self.project_mgr = ProjectManager()

        # Widget Central (Pestañas)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # --- 1. PESTAÑA INICIO ---
        self.tab_home = QWidget()
        self.setup_project_ui() 
        self.tabs.addTab(self.tab_home, "1. Inicio")
        
        # --- 2. PESTAÑA CONFIGURACIÓN (Packmol) ---
        self.setup_tab = SetupTab() 
        self.tabs.addTab(self.setup_tab, "2. Setup (Packmol)")
        
        # --- 3. PESTAÑA TOPOLOGÍA (GROMACS) ---
        self.topo_tab = TopologyTab()
        self.tabs.addTab(self.topo_tab, "3. Topología")
        
        # --- 4. PESTAÑA SIMULACIÓN (MDP + Run) ---
        self.sim_tab = SimulationTab()
        self.tabs.addTab(self.sim_tab, "4. Simulación (Run)")
        
        # Bloquear pestañas hasta que se cree un proyecto
        self.tabs.setTabEnabled(1, False) 
        self.tabs.setTabEnabled(2, False) 
        self.tabs.setTabEnabled(3, False) 
        
        # Conectar evento de cambio de pestaña
        self.tabs.currentChanged.connect(self.on_tab_changed)

    def setup_project_ui(self):
        """Diseño visual de la pestaña Inicio"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        title = QLabel("Bienvenido al Gestor de Simulaciones")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)
        
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setStyleSheet("background-color: #f0f0f0; border-radius: 5px; padding: 10px;")
        panel_layout = QVBoxLayout()
        
        panel_layout.addWidget(QLabel("Paso 1: Defina el nombre del nuevo proyecto"))
        self.input_name = QLineEdit("Mi_Tesis_Simulacion_01")
        self.input_name.setStyleSheet("padding: 5px; font-size: 14px;")
        panel_layout.addWidget(self.input_name)
        
        panel_layout.addSpacing(10) 
        
        panel_layout.addWidget(QLabel("Paso 2: Seleccione dónde guardar la carpeta"))
        self.btn_create = QPushButton("📂 Seleccionar Ruta y Crear Proyecto")
        self.btn_create.setMinimumHeight(40)
        self.btn_create.setStyleSheet("background-color: #007bff; color: white; font-weight: bold;")
        self.btn_create.clicked.connect(self.create_project_handler)
        panel_layout.addWidget(self.btn_create)
        
        panel.setLayout(panel_layout)
        layout.addWidget(panel)
        
        layout.addSpacing(20)
        self.lbl_status = QLabel("Estado: Esperando creación de proyecto...")
        self.lbl_status.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.lbl_status)
        
        self.lbl_path_info = QLabel("")
        layout.addWidget(self.lbl_path_info)
        
        self.tab_home.setLayout(layout)

    def create_project_handler(self):
        """Maneja la creación del proyecto y activa las pestañas"""
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Escriba un nombre para el proyecto.")
            return

        root_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Raíz")
        
        if root_path:
            success, msg = self.project_mgr.create_project(name, root_path)
            
            if success:
                self.lbl_status.setText(f"✅ PROYECTO ACTIVO: {name}")
                self.lbl_status.setStyleSheet("color: green; font-weight: bold;")
                
                full_path = self.project_mgr.current_project_path
                self.lbl_path_info.setText(f"Ruta: {full_path}")
                
                # --- HABILITAR PESTAÑAS ---
                self.tabs.setTabEnabled(1, True)
                self.tabs.setTabEnabled(2, True)
                self.tabs.setTabEnabled(3, True)
                
                # --- PASAR DATOS DEL PROYECTO A LAS PESTAÑAS ---
                
                # 1. Setup Tab (Necesita ruta para guardar PDBs)
                self.setup_tab.set_active_project(full_path)
                
                # 2. Topology Tab (Necesita ruta para guardar .top)
                # Nota: TopologyTab obtiene datos al cambiar de pestaña (on_tab_changed)
                # pero podemos inicializar la ruta base aquí también si fuera necesario.
                
                # 3. Simulation Tab (Necesita ruta para guardar .mdp)
                self.sim_tab.update_project_data(self.project_mgr) 
                
                QMessageBox.information(self, "Proyecto Creado", f"Carpeta creada exitosamente:\n{full_path}")
            else:
                self.lbl_status.setText(f"❌ Error: {msg}")
                self.lbl_status.setStyleSheet("color: red;")

    def on_tab_changed(self, index):
        """Sincroniza datos cuando el usuario cambia de pestaña"""
        
        # Si entra a Topología (Index 2)
        if index == 2:
            # Traer las moléculas definidas en Setup
            mols = self.setup_tab.get_molecules_data()
            self.topo_tab.update_project_data(self.project_mgr, mols)
        
        # Si entra a Simulación (Index 3)
        if index == 3:
            # Asegurar que tenga el project manager actualizado
            self.sim_tab.update_project_data(self.project_mgr)