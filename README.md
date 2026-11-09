# Calculadora basada en gestos — Práctica 3

**Sistema operativo empleado:** macOS (Apple Silicon), ejecutado con **uv** y Python 3.12.

## Ejecución (macOS / Windows con uv)

Desde la carpeta raíz del proyecto:

```bash
uv venv                                        # crea el entorno con Python 3.12 ( python-version)
uv pip install -r requirements.txt             # instala las librerías con las versiones fijadas
uv run python src/gest-calc/webcam_test.py     # comprobar la cámara
uv run python src/gest-calc/sample_main.py     # ejecutar la calculadora
```

En macOS, la primera ejecución pide permiso de cámara para la Terminal: hay que aceptarlo y volver a lanzar.
Si se abre la cámara del iPhone (Cámara de Continuidad), cambiar `cv2.VideoCapture(0)` por `cv2.VideoCapture(1)`.

**Teclas:** `D` muestra/oculta la información de depuración · `Q` sale.

## Cómo se usa

1. Mostrar una mano a la cámara. Aparece un círculo blanco (el cursor) entre el pulgar y el índice.
2. Llevar el cursor sobre una tecla: se pone **azul**.
3. **Juntar pulgar e índice (pinza)** y mantener un momento: un anillo amarillo se llena y, al completarse, la tecla **destella en verde** y se pulsa.
4. **Separar los dedos** antes de pulsar la siguiente tecla.

## Decisiones de diseño

### Gesto
- **Pinza pulgar-índice + apuntar**: un vocabulario mínimo de gestos (solo uno), natural y fácil de distinguir
  de una mano abierta. Borrar (`<`) y reset (`C`) son teclas, así no hay gestos que memorizar.

### Detección
- **MediaPipe Hands** (`mp.solutions`, v0.10.21): 21 landmarks por mano. Una sola mano, confianza de detección 0,7
  y de seguimiento 0,6.
- **Ratio de pinza** = distancia(pulgar, índice) / tamaño de la palma (muñeca → nudillo del corazón).
  Medido: en píxeles la pinza variaba de 79 a 100 según la distancia a la cámara; normalizado se mantiene en ~0,07
  tanto cerca como lejos (**invariante a la escala**).
- **Cursor en el punto medio** entre pulgar e índice: al cerrar la pinza los dedos convergen ahí, así el gesto
  no desplaza el cursor fuera de la tecla.

### Evitar que acciones arbitrarias se interpreten como gestos
| Mecanismo | Valor | Qué evita |
|---|---|---|
| **Zona activa** | solo cuenta sobre una tecla | pinzas fuera de la calculadora |
| **Histéresis** | entra < 0,25, sale > 0,40 | parpadeo cuando la señal oscila cerca del umbral |
| **Confianza sostenida** (estado CANDIDATO) | 0,3 s | cierres accidentales; da tiempo a corregir |
| **Estado refractario** | soltar + 0,3 s | que una pinza pulse varias veces |
| **Tecla fijada** al empezar el candidato | — | que el movimiento al cerrar cambie de tecla |

Máquina de estados: `REPOSO → CANDIDATO → (pulsa una vez) → REFRACTARIO → REPOSO`.
El tiempo de confirmación se eligió probando 0,15, 0,2 y 0,3 s: con 0,3 s da tiempo a corregir una pinza accidental y el anillo de progreso se ve bien, con un retraso que no molesta.

### Feedback (usabilidad)
- Tecla apuntada en azul, anillo de progreso durante la confirmación, destello verde al pulsar.
- Línea de ayuda siempre visible y aviso cuando no se detecta la mano.
- Información de depuración (ratio, pinza, tecla, estado) oculta por defecto y activable con `D`.

### Calculadora
- La lógica está en la función `procesar_tecla()`, separada de la visión.
- **Prevención de errores**: no permite dos operadores seguidos (se sustituye el anterior), dos puntos en un número, empezar con un operador (salvo `-`) ni calcular una expresión incompleta. `84/2` muestra `42`, no `42.0`.
- `eval()` se mantiene porque solo pueden entrar caracteres de los botones; solo se captura `ZeroDivisionError`.

## Cambios respecto a los archivos proporcionados
- `sample_main.py`: implementada toda la detección de gestos, la máquina de estados, el feedback y la lógica de la calculadora. La distribución de los botones es la original.
- Lectura del primer fotograma con varios intentos (en macOS la cámara tarda en arrancar).
- `requirements.txt`, `Dockerfile` y `Makefile`: sin cambios.