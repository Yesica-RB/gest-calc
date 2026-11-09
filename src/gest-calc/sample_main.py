import cv2
import mediapipe as mp
import math
import time

# ---------- PARÁMETROS (ajustados probando con mi cámara) ----------
PINCH_ENTER = 0.25       # ratio por debajo del cual empieza la pinza
PINCH_EXIT = 0.40        # ratio por encima del cual termina (histéresis)
CONFIRM_TIME = 0.30      # segundos que hay que mantener la pinza (confianza sostenida)
REFRACTORY_TIME = 0.30   # segundos mínimos entre pulsaciones (estado refractario)
FLASH_TIME = 0.25        # duración del destello verde al pulsar

hands = mp.solutions.hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.6,
)

class Button:
    def __init__(self, pos, width, height, value):
        self.pos = pos
        self.width = width
        self.height = height
        self.value = value

    def draw(self, img, resaltado=False):
        s = self.height / 100
        color = (255, 200, 100) if resaltado else (225, 225, 225)       # azul si se apunta
        cv2.rectangle(img, self.pos, (self.pos[0] + self.width, self.pos[1] + self.height),
                      color, cv2.FILLED)
        cv2.rectangle(img, self.pos, (self.pos[0] + self.width, self.pos[1] + self.height),
                      (50, 50, 50), 3)

        text_x = self.pos[0] + self.width // 2 - int(15 * s)
        text_y = self.pos[1] + self.height // 2 + int(15 * s)

        cv2.putText(img, self.value, (text_x, text_y), cv2.FONT_HERSHEY_PLAIN,
                    3 * s, (50, 50, 50), max(1, round(3 * s)))

    def contains(self, point):
        x, y = point                                                # separamos el punto en x e y
        dentro_x = self.pos[0] <= x <= self.pos[0] + self.width     # entre izquierda y derecha
        dentro_y = self.pos[1] <= y <= self.pos[1] + self.height    # entre arriba y abajo
        return dentro_x and dentro_y                                # dentro si se cumplen las dos


OPERADORES = "+-*/"

def procesar_tecla(operation, tecla):
    """Recibe la operación actual y la tecla pulsada; devuelve la nueva operación."""
    if operation == "Error":                 # tras un error, se empieza de cero
        operation = ""

    if tecla == "C":                         # reset
        return ""

    if tecla == "<":                         # borrar el último carácter
        return operation[:-1]

    if tecla == "=":
        if operation in ("", "-") or operation[-1] in OPERADORES:
            return operation                 # expresión incompleta: no hacemos nada
        try:
            resultado = eval(operation)      # seguro: solo entran caracteres de los botones
        except ZeroDivisionError:
            return "Error"
        return f"{resultado:.10g}"           # 42.0 -> "42", 0.1+0.2 -> "0.3"

    if tecla in OPERADORES:
        if operation in ("", "-"):           # solo se puede empezar con un negativo
            return "-" if tecla == "-" else ""
        if operation[-1] in OPERADORES:      # "3+" y pulso "*" -> "3*" (sustituye)
            return operation[:-1] + tecla
        return operation + tecla

    if tecla == ".":
        numero_actual = operation            # el número que se está escribiendo:
        for op in OPERADORES:                # lo que hay después del último operador
            numero_actual = numero_actual.split(op)[-1]
        if "." in numero_actual:             # ese número ya tiene punto -> ignorar
            return operation
        if numero_actual == "":              # "." al principio -> "0."
            return operation + "0."
        return operation + "."

    return operation + tecla                 # es un dígito


# MUST be configured for each system
cap = cv2.VideoCapture(0)

#input image size, based on your webcam
WIDTH = 1920
HEIGHT = 1080
cap.set(3, WIDTH)
cap.set(4, HEIGHT)

# En macOS la cámara tarda un momento en arrancar: damos varios intentos
for intento in range(30):
    success, img = cap.read()
    if success:
        break
if not success:
    print("Failed to read frame")
    exit(1)
HEIGHT, WIDTH = img.shape[:2]
scale = HEIGHT / 1080
size = int(100 * scale)

# basic list of buttons, may be changed (changes must be justified)
buttonListValues = [['C', '<'],
                    ['7', '8', '9', '/'],  # ÷ cant be rendered, so well have to do with / :/
                    ['4', '5', '6', '*'],
                    ['1', '2', '3', '-'],
                    ['0', '.', '=', '+']]

buttonlist = []
for y in range(5):
    for x in range(4):
        if y == 0 and x >= 2:  # first row only has 2 buttons (C and <), so kinda special case
            break

        xpos = int(WIDTH - 5 * size + x * size)
        ypos = int(HEIGHT * 0.15 + y * size)

        # first row special case, second button needs to be shifted
        if y == 0 and x == 1: #not the most elegant
            xpos += size

        if y == 0:
            width = 2 * size
            buttonlist.append(Button((xpos, ypos), width, size, buttonListValues[y][x]))
        else:
            buttonlist.append(Button((xpos, ypos), size, size, buttonListValues[y][x]))

operation = ""
pinza = False            # estado de la pinza (se recuerda entre fotogramas)
estado = "REPOSO"        # REPOSO, CANDIDATO o REFRACTARIO
tecla_objetivo = None    # tecla fijada al empezar el candidato
t_inicio = 0.0           # cuándo empezó el candidato
t_pulsacion = 0.0        # cuándo fue la última pulsación
tecla_pulsada = None     # última tecla pulsada (para el destello)
t_destello = 0.0         # cuándo empezó el destello
mostrar_debug = False    # textos de depuración (se activan con la tecla D)

while True:
    success, img = cap.read()
    if not success:
        print("Failed to read frame")
        break

    # ---------- 1. PERCEPCIÓN: ver la mano ----------
    img = cv2.flip(img, 1)                       # efecto espejo
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)   # MediaPipe espera RGB
    result = hands.process(rgb)

    # ---------- 2. RASGOS: cursor y pinza ----------
    cursor = None                                # por defecto: no hay mano
    if result.multi_hand_landmarks:              # ¿hay alguna mano?
        mano = result.multi_hand_landmarks[0]

        # Punta del índice (landmark 8)
        punta = mano.landmark[8]
        x = int(punta.x * WIDTH)
        y = int(punta.y * HEIGHT)

        # Punta del pulgar (landmark 4)
        pulgar = mano.landmark[4]
        px = int(pulgar.x * WIDTH)
        py = int(pulgar.y * HEIGHT)

        # Cursor en el punto medio: al cerrar la pinza los dedos convergen ahí,
        # así el propio gesto no mueve el cursor fuera de la tecla
        cursor = ((x + px) // 2, (y + py) // 2)

        # Distancia pulgar-índice en píxeles
        distancia = math.hypot(x - px, y - py)

        # Tamaño de la palma: muñeca (0) -> nudillo del corazón (9)
        muneca = mano.landmark[0]
        mx = int(muneca.x * WIDTH)
        my = int(muneca.y * HEIGHT)
        nudillo = mano.landmark[9]
        nx = int(nudillo.x * WIDTH)
        ny = int(nudillo.y * HEIGHT)
        palma = math.hypot(mx - nx, my - ny)

        # Ratio: distancia entre dedos medida en "palmas" (invariante a la distancia a la cámara)
        ratio = distancia / palma

        # Histéresis: entra por debajo de PINCH_ENTER, sale por encima de PINCH_EXIT
        if not pinza and ratio < PINCH_ENTER:
            pinza = True
        elif pinza and ratio > PINCH_EXIT:
            pinza = False
    else:                                        # no hay mano
        pinza = False

    # ---------- 3. ¿QUÉ TECLA HAY BAJO EL CURSOR? ----------
    hovered = None                               # None = ninguna
    if cursor is not None:
        for button in buttonlist:
            if button.contains(cursor):
                hovered = button.value

    # ---------- 4. MÁQUINA DE ESTADOS ----------
    ahora = time.time()
    something = False
    received_val = ""

    if estado == "REPOSO":
        if pinza and hovered is not None:            # empieza una pinza sobre una tecla
            estado = "CANDIDATO"
            tecla_objetivo = hovered                 # fijamos la tecla
            t_inicio = ahora

    elif estado == "CANDIDATO":
        if not pinza:                                # soltó demasiado pronto -> accidental
            estado = "REPOSO"
        elif ahora - t_inicio >= CONFIRM_TIME:       # mantenida suficiente -> ¡pulsar!
            something = True
            received_val = tecla_objetivo
            estado = "REFRACTARIO"
            t_pulsacion = ahora

    elif estado == "REFRACTARIO":
        if not pinza and ahora - t_pulsacion >= REFRACTORY_TIME:
            estado = "REPOSO"                        # listo para la siguiente

    # ---------- 5. CALCULADORA ----------
    if something:
        tecla_pulsada = received_val                 # guardamos para el destello
        t_destello = ahora
        operation = procesar_tecla(operation, received_val)

    # ---------- 6. DIBUJAR (siempre al final) ----------
    operation_x = int(WIDTH - 5 * size)
    operation_y = int(HEIGHT * 0.05)

    cv2.rectangle(img, (operation_x, operation_y), (operation_x + 4 * size, operation_y + int(1.2 * size)),
                  (225, 225, 225), cv2.FILLED)
    cv2.rectangle(img, (operation_x, operation_y), (operation_x + 4 * size, operation_y + int(1.2 * size)),
                  (50, 50, 50), 3)
    cv2.putText(img, operation, (operation_x + int(0.1 * size), operation_y + int(0.75 * size)),
                cv2.FONT_HERSHEY_PLAIN, 3 * scale, (50, 50, 50), max(1, round(3 * scale)))

    for button in buttonlist:
        button.draw(img, resaltado=(button.value == hovered))

    # Destello verde en la tecla pulsada
    if tecla_pulsada is not None and ahora - t_destello < FLASH_TIME:
        for button in buttonlist:
            if button.value == tecla_pulsada:
                x1, y1 = button.pos
                cv2.rectangle(img, (x1, y1), (x1 + button.width, y1 + button.height),
                              (0, 200, 0), 8)

    if cursor is not None:                       # cursor encima de todo
        cv2.circle(img, (x, y), 8, (255, 0, 255), cv2.FILLED)           # yema del índice
        cv2.circle(img, (px, py), 8, (255, 0, 0), cv2.FILLED)           # yema del pulgar
        cv2.circle(img, cursor, 15, (255, 255, 255), 3)                 # cursor (punto medio)

        # Anillo que se llena durante CANDIDATO
        if estado == "CANDIDATO":
            progreso = min(1.0, (ahora - t_inicio) / CONFIRM_TIME)
            cv2.ellipse(img, cursor, (30, 30), -90, 0, 360 * progreso, (0, 255, 255), 6)

    # Textos de depuración (tecla D)
    if mostrar_debug:
        if cursor is not None:
            cv2.putText(img, f"ratio {ratio:.2f}", (50, 100),
                        cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 0), 3)
        cv2.putText(img, f"pinza: {pinza}", (50, 160),
                    cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)
        cv2.putText(img, f"tecla: {hovered}", (50, 220),
                    cv2.FONT_HERSHEY_PLAIN, 3, (255, 255, 0), 3)
        cv2.putText(img, f"estado: {estado}", (50, 280),
                    cv2.FONT_HERSHEY_PLAIN, 3, (0, 255, 255), 3)

    # Ayuda siempre visible abajo
    cv2.putText(img, "Apunta a una tecla y junta pulgar e indice   |   D: depuracion   Q: salir",
                (20, HEIGHT - 20), cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 2)

    # Aviso si no se ve la mano
    if cursor is None:
        cv2.putText(img, "Muestra la mano a la camara", (20, HEIGHT - 70),
                    cv2.FONT_HERSHEY_PLAIN, 2, (0, 255, 255), 2)

    cv2.imshow('Calculator', img)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break
    elif key == ord('d'):
        mostrar_debug = not mostrar_debug    # activa/desactiva la depuración