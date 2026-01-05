import sys
from PyQt6.QtWidgets import QApplication
from src.view.main_window import MainWindow

def main():
    # Inicializar la aplicación Qt
    app = QApplication(sys.argv)
    
    # Aplicar un estilo (Fusion es limpio y funciona bien en Linux)
    app.setStyle("Fusion")
    
    # Crear y mostrar ventana
    window = MainWindow()
    window.show()
    
    # Loop principal
    sys.exit(app.exec())

if __name__ == "__main__":
    main()