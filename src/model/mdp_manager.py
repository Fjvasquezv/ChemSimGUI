import os
import re

class MdpManager:
    def __init__(self, templates_dir):
        self.templates_dir = templates_dir

    def get_template_content(self, template_name):
        path = os.path.join(self.templates_dir, f"{template_name}.mdp")
        if not os.path.exists(path):
            return f"; Error: No se encontró {path}"
        with open(path, 'r') as f:
            return f.read()

    def save_mdp(self, output_path, content):
        try:
            with open(output_path, 'w') as f:
                f.write(content)
            return True, f"Guardado en {os.path.basename(output_path)}"
        except Exception as e:
            return False, str(e)

    def update_parameters(self, content, params_dict):
        """
        Recibe un texto MDP y un diccionario {clave: valor}.
        Actualiza los valores respetando comentarios y formato.
        """
        lines = content.split('\n')
        new_lines = []
        
        # Marcamos qué llaves ya encontramos para evitar duplicados
        keys_found = set()

        for line in lines:
            clean_line = line.split(';')[0].strip()
            
            # Detectar si la línea empieza con alguna de nuestras claves
            key_match = None
            for key in params_dict:
                # Usamos regex para asegurar palabra completa (ej: evitar confundir 'tau_t' con 'tau_p')
                # Buscamos "key" al inicio seguida de espacios o =
                if re.match(f"^{key}\\s*(=|$)", clean_line):
                    key_match = key
                    break
            
            if key_match:
                # Reconstruir línea conservando comentarios
                val = str(params_dict[key_match])
                comment = ""
                if ";" in line:
                    comment = " ;" + line.split(';', 1)[1]
                
                # Formato alineado: Clave (15 espacios) = Valor (Comentario)
                new_lines.append(f"{key_match:<20} = {val}{comment}")
                keys_found.add(key_match)
            else:
                new_lines.append(line)
        
        # Opcional: Si quisieras agregar claves que no existían, podrías hacerlo aquí
        return '\n'.join(new_lines)