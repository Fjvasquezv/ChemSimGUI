# Función de Reconstrucción de Árbol de Simulaciones

## ¿Qué es?

La función **"Reconstruir Árbol"** es una herramienta de recuperación integrada en ChemSimGUI que reconstruye automáticamente la estructura jerárquica del árbol de simulaciones (`simulation_state.tree_data`) escaneando el contenido del directorio `storage/` del proyecto.

## ¿Cuándo usarla?

- El JSON del proyecto se corrompió y los nodos de simulación se perdieron
- Hay inconsistencias entre los archivos en `storage/` y los nodos en el árbol
- Se agregaron archivos manualmente a `storage/` y necesitas sincronizarlos con el árbol
- El árbol muestra nodos fantasma que no corresponden a archivos reales

## ¿Cómo usarla?

### Desde la UI:

1. **Cargar un proyecto** (pestaña "1. Proyecto")
2. En la barra de sistema (debajo del combo de sistemas activos), encontrarás el botón naranja **"🔧 Reconstruir Árbol"**
3. Hacer clic en el botón abrirá un diálogo preguntando:
   - **"Sistema actual"**: Reconstruye solo el sistema actualmente seleccionado
   - **"Todos los sistemas"**: Reconstruye el árbol para todos los sistemas del proyecto
4. El programa escaneará `storage/` y reconstruirá el árbol automáticamente
5. Se mostrará un mensaje con el resumen de cambios

### Desde código (programáticamente):

```python
from src.model.project_manager import ProjectManager

pm = ProjectManager()
pm.load_project_from_path('/ruta/al/proyecto')

# Reconstruir solo un sistema
success, msg = pm.rebuild_tree_from_storage('X=0.04')

# Reconstruir todos los sistemas
success, msg = pm.rebuild_tree_from_storage()

if success:
    print("Éxito:", msg)
else:
    print("Error:", msg)
```

## Reglas de Reconstrucción

### Archivos válidos (incluidos en el árbol):

- `minim` - Minimización
- `gen`, `gen###.#` - Generación (ej: gen258.1)
- `equil`, `equil###.#` - Equilibración (ej: equil258.1)
- `prod`, `prod###.#`, `prod###.#_rdf_batch_*` - Producción (ej: prod258.1, prod258.1_rdf_batch_0_1769529200)

### Archivos excluidos (NO incluidos):

- Cualquier archivo con `_prev` (versiones previas/antiguas)
- `topol`, `system_init`, `CBD`, `PEN`, `index`, `mdout`, etc.
- Cualquier archivo que no sea parte de simulaciones GROMACS

### Asignación de Temperatura:

- Nodos con números en su nombre: la temperatura se extrae del número
  - `gen258.1` → T=258K
  - `prod301.1` → T=301K
- Nodos genéricos sin número: se asigna T=253K
  - `gen` → T=253K
  - `equil` → T=253K
  - `prod` → T=253K

### Jerarquía:

```
minim (1 por composición)
├── gen (varios, agrupados por temperatura)
│   ├── equil (agrupados por temperatura de su parent gen)
│   │   ├── prod (agrupados por temperatura)
│   │   └── prod_rdf_batch_* (derivados de equil)
│   └── equil (otros, diferentes temperatura)
│       └── prod
└── gen (temperaturas adicionales)
    └── ...
```

## Cuidados

- **Backup automático**: Antes de guardar cambios, se crea un backup en `project_db.json.bak.clean.<timestamp>`
- **No destructivo en almacenamiento**: La reconstrucción del árbol NO modifica, elimina ni crea archivos en `storage/`. Solo actualiza la estructura del JSON.
- **Reconstrucción completa**: Si ejecutas sin especificar un sistema, se reconstruyen TODOS los sistemas a la vez
- **_prev excluidos**: Cualquier archivo con sufijo `_prev` es ignorado (son versiones antiguas/previas)

## Ejemplo de Uso

```python
# Proyecto con corrupción en X=0.04
pm = ProjectManager()
pm.load_project_from_path('/media/francisco/TOSHIBA EXT1/Maestría/Mezclas/Pentano')

# Reconstruir solo X=0.04
ok, msg = pm.rebuild_tree_from_storage('X=0.04')
# Resultado: X=0.04: 12 → 12 nodos

# Reconstruir todos
ok, msg = pm.rebuild_tree_from_storage()
# Resultado: Se reconstruyen Default_System, X=0.02, X=0.04, X=0.06, ...
```

## Nota Técnica

La función está disponible en:
- **Clase**: `ProjectManager` (`src/model/project_manager.py`)
- **Método**: `rebuild_tree_from_storage(system_name=None)`
- **UI**: Botón en la barra de sistema de `MainWindow` (`src/view/main_window.py`)
