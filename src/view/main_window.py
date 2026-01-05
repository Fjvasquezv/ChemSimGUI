import sys
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFileDialog, QMessageBox, QTabWidget)
from src.model.project_manager import ProjectManager

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulador Tesis Ing. Química")
        self.setGeometry(100, 100, 800, 600)
        
        # Lógica
        self.project_mgr = ProjectManager()

        # UI Central
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Inicializar Pestañas
        self.setup_project_tab()
        self.setup_simulation_tab()

    def setup_project_tab(self):
        """Pestaña 1: Gestión de Proyecto (CU-01)"""
        tab = QWidget()
        layout = QVBoxLayout()
        
        layout.addWidget(QLabel("<h2>Gestión de Proyecto</h2>"))
        layout.addWidget(QLabel("Nombre del Proyecto:"))
        
        self.input_name = QLineEdit("Nuevo_Proyecto_Tesis")
        layout.addWidget(self.input_name)
        
        btn_create = QPushButton("Crear / Seleccionar Directorio")
        btn_create.clicked.connect(self.create_project_handler)
        layout.addWidget(btn_create)
        
        self.lbl_status = QLabel("Estado: Esperando...")
        layout.addWidget(self.lbl_status)
        
        layout.addStretch()
        self.tabs.addTab(tab, "Inicio")

    def setup_simulation_tab(self):
        """Pestaña 2: Placeholder para futuras simulaciones"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<h2>Configuración de Simulación</h2>"))
        layout.addWidget(QLabel("Aquí irán las opciones de Packmol y GROMACS..."))
        layout.addStretch()
        self.tabs.addTab(tab, "Simulación")

    def create_project_handler(self):
        # Abrir dialogo para elegir carpeta donde guardar el proyecto
        root_path = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta Raíz")
        
        if root_path:
            name = self.input_name.text()
            success, msg = self.project_mgr.create_project(name, root_path)
            
            if success:
                self.lbl_status.setText(f"Activo: {msg}")
                self.lbl_status.setStyleSheet("color: green")
                QMessageBox.information(self, "Éxito", msg)
            else:
                self.lbl_status.setText(f"Error: {msg}")
                self.lbl_status.setStyleSheet("color: red")