from PyQt6.QtCore import QThread, pyqtSignal
import subprocess
import os

class CommandWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, command_list, working_dir, input_file_path=None):
        super().__init__()
        self.command = command_list
        self.wd = working_dir
        self.input_file_path = input_file_path
        self.process = None

    def run(self):
        file_obj = None
        try:
            if self.input_file_path:
                try:
                    file_obj = open(self.input_file_path, 'r')
                except FileNotFoundError:
                    self.finished_signal.emit(False, f"Input no encontrado: {self.input_file_path}")
                    return

            self.log_signal.emit(f"CMD: {' '.join(self.command)}")
            
            # Ejecución estándar (Estable)
            self.process = subprocess.Popen(
                self.command,
                cwd=self.wd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Fusionar errores y output
                stdin=file_obj,
                text=True,    # Modo texto normal
                bufsize=1     # Buffer de línea (estándar)
            )

            # Leer línea a línea
            while True:
                line = self.process.stdout.readline()
                if not line and self.process.poll() is not None:
                    break
                if line:
                    self.log_signal.emit(line.strip())

            rc = self.process.poll()
            if file_obj: file_obj.close()

            if rc == 0:
                self.finished_signal.emit(True, "Proceso finalizado correctamente.")
            elif rc == -15:
                self.finished_signal.emit(False, "Proceso detenido por el usuario.")
            else:
                self.finished_signal.emit(False, f"Error: Código de salida {rc}")

        except Exception as e:
            if file_obj: file_obj.close()
            self.finished_signal.emit(False, f"Error crítico: {str(e)}")

    def stop_process(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()