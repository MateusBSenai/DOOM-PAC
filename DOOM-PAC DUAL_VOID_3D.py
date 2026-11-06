import sys
import math
import random
import json
import os
import pygame

# Inicialização
pygame.init()
pygame.joystick.init()
pygame.mixer.init()

# --- CONFIGURAÇÃO DAS TELAS E RESOLUÇÕES ---
VIEW_W = 1920
VIEW_H = 1000  # Altura de cada tela (Total Interno = 2000px)
TOTAL_H = VIEW_H * 2

RESOLUTIONS = [(1920, 2000), (1280, 1400), (960, 1000)]
curr_res_idx = 0
is_fullscreen = False

screen = pygame.display.set_mode(RESOLUTIONS[curr_res_idx], pygame.RESIZABLE)
pygame.display.set_caption("DOOM-PAC: DUAL VOID 3D - Official Arcade v12.0")

surf_top_3d = pygame.Surface((480, 250))  # Buffer low-res 3D retro
surf_bottom_2d = pygame.Surface((VIEW_W, VIEW_H))
full_canvas = pygame.Surface((VIEW_W, TOTAL_H))

# Configurações de Rotação e Troca de Telas
swap_screens = False    # True = 3D Embaixo / 2D Em Cima
rotation_angle = 0      # 0, 90, 180, 270 graus

# --- ESTADOS DO JOGO ---
STATE_MENU = 0
STATE_CUSTOMIZE = 1
STATE_PLAYING = 2
STATE_PAUSED = 3
STATE_GAMEOVER = 4
game_state = STATE_MENU
is_coop_mode = False

cust_player = 1
active_text_input = ""

# --- SISTEMA DE ROUNDS E PALETA DE CORES ---
current_round = 1
round_banner_timer = 0
ROUND_COLORS = [
    (30, 80, 220),   # R1: Azul Clássico
    (30, 200, 80),   # R2: Verde Neon
    (180, 50, 220),  # R3: Roxo Místico
    (0, 220, 220),   # R4: Ciano Elétrico
    (220, 180, 30),  # R5: Dourado
    (220, 40, 120),  # R6: Magenta
    (255, 128, 0)    # R7: Laranja Vulcânico
]

def get_current_wall_color():
    return ROUND_COLORS[(current_round - 1) % len(ROUND_COLORS)]

# --- CARREGAMENTO DE FONTES ---
FONT_FILENAME = "DeterminationMonoWebRegular-Z5oq.ttf"

def get_font(size):
    if os.path.exists(FONT_FILENAME):
        try: return pygame.font.Font(FONT_FILENAME, size)
        except Exception: pass
    return pygame.font.SysFont("Arial", size, bold=True)

font_hud = get_font(24)
font_large = get_font(36)
font_title = get_font(56)

# --- ARQUIVO DE PLACAR EXCLUSIVO ---
HIGHSCORE_FILE = "doom_pac_highscores.json"

def load_highscores():
    default_hs = {
        "solo": [{"name": "---", "score": 0, "round": 1} for _ in range(5)],
        "coop": [{"name": "---", "score": 0, "round": 1} for _ in range(5)]
    }
    if os.path.exists(HIGHSCORE_FILE):
        try:
            with open(HIGHSCORE_FILE, "r") as f:
                data = json.load(f)
                while len(data.setdefault("solo", [])) < 5:
                    data["solo"].append({"name": "---", "score": 0, "round": 1})
                while len(data.setdefault("coop", [])) < 5:
                    data["coop"].append({"name": "---", "score": 0, "round": 1})
                return data
        except Exception:
            pass
    return default_hs

def save_highscores(hs_data):
    try:
        with open(HIGHSCORE_FILE, "w") as f:
            json.dump(hs_data, f, indent=4)
    except Exception:
        pass

highscores = load_highscores()

def check_and_update_highscores():
    if is_coop_mode:
        total_score = p1["score"] + p2["score"]
        rec_name = f"{p1['name']} & {p2['name']}"
        mode_key = "coop"
    else:
        total_score = p1["score"]
        rec_name = p1["name"]
        mode_key = "solo"

    scores_list = highscores.get(mode_key, [])
    scores_list.append({"name": rec_name, "score": total_score, "round": current_round})
    scores_list.sort(key=lambda x: x["score"], reverse=True)
    highscores[mode_key] = scores_list[:5]
    save_highscores(highscores)

def check_game_over():
    global game_state
    if game_state == STATE_PLAYING:
        p1_dead = (p1["hp"] <= 0)
        p2_dead = (p2["hp"] <= 0) if is_coop_mode else True
        if p1_dead and p2_dead:
            check_and_update_highscores()
            game_state = STATE_GAMEOVER

# --- CONTROLES ---
joysticks = []
def update_joysticks():
    global joysticks
    joysticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
    for j in joysticks:
        j.init()

update_joysticks()

# --- ÁUDIO ---
def generate_synth_sound(freq=440, duration=0.08, vol=0.1):
    sample_rate = 22050
    n_samples = int(sample_rate * duration)
    buf = bytearray()
    for i in range(n_samples):
        t = i / sample_rate
        val = int(127 + 127 * math.sin(2 * math.pi * freq * t))
        buf.append(val)
    try:
        snd = pygame.mixer.Sound(buffer=bytes(buf))
        snd.set_volume(vol)
        return snd
    except Exception:
        return None

sfx_shoot_pistol = generate_synth_sound(220, 0.08, 0.15)
sfx_shoot_shotgun = generate_synth_sound(100, 0.22, 0.30)
sfx_hit = generate_synth_sound(120, 0.15, 0.20)
sfx_pickup = generate_synth_sound(800, 0.05, 0.08)
sfx_menu = generate_synth_sound(600, 0.05, 0.10)
sfx_revive = generate_synth_sound(950, 0.20, 0.15)
sfx_teleport = generate_synth_sound(1200, 0.15, 0.15)

def play_sfx(sfx):
    if sfx:
        try: sfx.play()
        except Exception: pass

# --- MAPA DO LABIRINTO (21x20 BLOCOS) ---
MAZE_LAYOUT = [
    "111111111111111111111",
    "12222>2221222<2222221",
    "121312111212111213121",
    "121112131212131211121",
    "1222222222>2222222221",
    "121112131111131211121",
    "122222122212221222221",
    "111112111010111211111",
    "000012100000001210000",
    "111112101101101211111",
    "T0000200100010020000T",
    "111112101111101211111",
    "000012100000001210000",
    "111112121111121211111",
    "1222222222<2222222221",
    "121312111212111213121",
    "122212222202222212221",
    "111212132111231212111",
    "122222122212221222221",
    "111111111111111111111"
]

MAP_W = len(MAZE_LAYOUT[0])
MAP_H = len(MAZE_LAYOUT)
grid_map = []
pellets = []
one_ways = []
teleports = []

def get_tile_type(x, y):
    mx, my = int(x), int(y)
    if 0 <= mx < MAP_W and 0 <= my < MAP_H:
        return grid_map[my][mx]
    return 1

def is_wall(x, y):
    t = get_tile_type(x, y)
    return t == 1 or t == 3

def check_one_way_block(curr_x, curr_y, move_dx, move_dy):
    tile = get_tile_type(curr_x, curr_y)
    if tile == '>' and move_dx < -0.01: return True
    if tile == '<' and move_dx > 0.01: return True
    if tile == 'v' and move_dy < -0.01: return True
    if tile == '^' and move_dy > 0.01: return True
    return False

def check_teleport(p):
    if get_tile_type(p["x"], p["y"]) == 'T':
        if p["x"] < 2.0:
            p["x"] = MAP_W - 1.5
            play_sfx(sfx_teleport)
        elif p["x"] > MAP_W - 2.0:
            p["x"] = 1.5
            play_sfx(sfx_teleport)

def reset_map():
    global grid_map, pellets, one_ways, teleports
    grid_map = []
    pellets = []
    one_ways = []
    teleports = []
    for r in range(MAP_H):
        row = []
        for c in range(MAP_W):
            ch = MAZE_LAYOUT[r][c] if c < len(MAZE_LAYOUT[r]) else '1'
            if ch == '1': row.append(1)
            elif ch == '3': row.append(3)
            elif ch in ('>', '<', 'v', '^'):
                row.append(ch)
                one_ways.append({"x": c + 0.5, "y": r + 0.5, "type": ch})
            elif ch == 'T':
                row.append('T')
                teleports.append({"x": c + 0.5, "y": r + 0.5})
            else:
                row.append(0)
                if ch == '2':
                    pellets.append({"x": c + 0.5, "y": r + 0.5})
        grid_map.append(row)

reset_map()

# --- JOGADORES ---
MAX_HP_CAP = 150

p1 = {
    "name": "P1", "x": 1.5, "y": 1.5, "angle": 0.0,
    "hp": 100, "ammo": 50, "score": 0, "weapon": 0,
    "shoot_timer": 0, "invulnerable": 0, "color": (255, 40, 40)
}

p2 = {
    "name": "P2", "x": 2.5, "y": 1.5, "angle": 0.0,
    "hp": 100, "ammo": 50, "score": 0, "weapon": 0,
    "shoot_timer": 0, "invulnerable": 0, "color": (40, 180, 255)
}

def start_new_game():
    global game_state, current_round, round_banner_timer
    current_round = 1
    round_banner_timer = 120
    reset_map()

    p1["x"], p1["y"], p1["angle"] = 1.5, 1.5, 0.0
    p1["hp"], p1["ammo"], p1["score"] = 100, 50, 0
    p1["shoot_timer"], p1["invulnerable"] = 0, 0

    p2["x"], p2["y"], p2["angle"] = 2.5, 1.5, 0.0
    p2["hp"] = 100 if is_coop_mode else 0
    p2["ammo"], p2["score"] = 50, 0
    p2["shoot_timer"], p2["invulnerable"] = 0, 0

    spawn_ghosts()
    game_state = STATE_PLAYING

def check_clear_pellets():
    global current_round, round_banner_timer
    if len(pellets) == 0:
        current_round += 1
        round_banner_timer = 120
        play_sfx(sfx_revive)

        active_players = [p1, p2] if is_coop_mode else [p1]
        for p in active_players:
            if p["hp"] <= 0:
                p["hp"] = 50
                p["invulnerable"] = 60
            else:
                p["hp"] = min(MAX_HP_CAP, p["hp"] + 50)

        reset_map()
        spawn_ghosts()

# --- TIROS E CÁLCULO DE DANO POR DISTÂNCIA ---
def check_los(x1, y1, x2, y2):
    dist = math.hypot(x2 - x1, y2 - y1)
    steps = int(dist * 12)
    if steps == 0: return True
    dx = (x2 - x1) / steps
    dy = (y2 - y1) / steps
    cx, cy = x1, y1
    for _ in range(steps):
        cx += dx
        cy += dy
        if is_wall(cx, cy):
            return False
    return True

def shoot_weapon(p):
    if p["hp"] <= 0 or p["shoot_timer"] > 0:
        return

    # PISTOLA (Arma 0)
    if p["weapon"] == 0:
        if p["ammo"] < 1: return
        p["ammo"] -= 1
        p["shoot_timer"] = 8
        play_sfx(sfx_shoot_pistol)
        max_dist = 12.0

    # SHOTGUN (Arma 1)
    else:
        if p["ammo"] < 3: return
        p["ammo"] -= 3
        p["shoot_timer"] = 35
        play_sfx(sfx_shoot_shotgun)
        max_dist = 8.0

    center_angle = p["angle"]
    for g in ghosts:
        if g["respawn"] == 0:
            gdx = g["x"] - p["x"]
            gdy = g["y"] - p["y"]
            g_dist = math.hypot(gdx, gdy)
            g_angle = math.atan2(gdy, gdx) - center_angle

            while g_angle > math.pi: g_angle -= 2 * math.pi
            while g_angle < -math.pi: g_angle += 2 * math.pi

            if abs(g_angle) < 0.35 and g_dist <= max_dist:
                if check_los(p["x"], p["y"], g["x"], g["y"]):
                    # CÁLCULO DE DANO POR DISTÂNCIA
                    if p["weapon"] == 0:  # Pistola (Dano equilibrado a longa distância)
                        damage = 1.5 if g_dist < 6.0 else 1.0
                    else:  # Shotgun (Devastadora de perto, fraca de longe)
                        if g_dist < 2.5: damage = 5.0    # 1 Hit-kill no fantasma!
                        elif g_dist < 5.0: damage = 3.0
                        else: damage = 1.0

                    g["hp"] -= damage
                    g["flash"] = 6
                    play_sfx(sfx_hit)

                    if g["hp"] <= 0:
                        g["respawn"] = 300
                        g["hp"] = 5  # HP base resetado para 5
                        p["score"] += 200

# --- FANTASMAS (MÁX HP = 5) ---
GHOST_COLORS = [
    (255, 40, 40),   # Blinky - Vermelho
    (255, 180, 255), # Pinky - Rosa
    (0, 255, 255),   # Inky - Ciano
    (255, 140, 0)    # Clyde - Laranja
]

ghosts = []
def spawn_ghosts():
    global ghosts
    ghosts = [
        {"x": 9.5, "y": 8.5, "dir": (1, 0), "color": GHOST_COLORS[0], "hp": 5, "respawn": 0, "flash": 0},
        {"x": 10.5, "y": 8.5, "dir": (-1, 0), "color": GHOST_COLORS[1], "hp": 5, "respawn": 0, "flash": 0},
        {"x": 8.5, "y": 8.5, "dir": (0, 1), "color": GHOST_COLORS[2], "hp": 5, "respawn": 0, "flash": 0},
        {"x": 11.5, "y": 8.5, "dir": (0, -1), "color": GHOST_COLORS[3], "hp": 5, "respawn": 0, "flash": 0}
    ]

spawn_ghosts()

def update_ghost_ai(g):
    if g["respawn"] > 0:
        g["respawn"] -= 1
        return

    if g.get("flash", 0) > 0: g["flash"] -= 1

    speed = 0.038 + (current_round - 1) * 0.002
    curr_x, curr_y = g["x"], g["y"]
    dir_x, dir_y = g["dir"]

    next_x = curr_x + dir_x * speed
    next_y = curr_y + dir_y * speed

    hit_wall = is_wall(next_x + dir_x * 0.3, next_y + dir_y * 0.3)

    tile_cx = int(curr_x) + 0.5
    tile_cy = int(curr_y) + 0.5
    at_center = math.hypot(curr_x - tile_cx, curr_y - tile_cy) < 0.08

    if hit_wall or at_center:
        targets = [p for p in (p1, p2 if is_coop_mode else p1) if p["hp"] > 0]
        target = min(targets, key=lambda p: math.hypot(p["x"] - curr_x, p["y"] - curr_y)) if targets else p1

        valid_dirs = []
        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            if (dx, dy) == (-dir_x, -dir_y) and not hit_wall:
                continue
            if not is_wall(curr_x + dx * 0.6, curr_y + dy * 0.6):
                valid_dirs.append((dx, dy))

        if valid_dirs:
            best_dir = valid_dirs[0]
            best_dist = 9999
            for dx, dy in valid_dirs:
                target_x = curr_x + dx
                target_y = curr_y + dy
                dist = math.hypot(target_x - target["x"], target_y - target["y"])
                if dist < best_dist:
                    best_dist = dist
                    best_dir = (dx, dy)
            g["dir"] = best_dir
            dir_x, dir_y = g["dir"]

    g["x"] += dir_x * speed
    g["y"] += dir_y * speed

    if get_tile_type(g["x"], g["y"]) == 'T':
        if g["x"] < 2.0: g["x"] = MAP_W - 1.5
        elif g["x"] > MAP_W - 2.0: g["x"] = 1.5

    for p in (p1, p2 if is_coop_mode else p1):
        if p["hp"] > 0 and p["invulnerable"] == 0:
            if math.hypot(g["x"] - p["x"], g["y"] - p["y"]) < 0.5:
                p["hp"] = max(0, p["hp"] - 15)
                p["invulnerable"] = 40
                play_sfx(sfx_hit)

# --- MOTOR DE RAYCASTING 3D PARAMETRIZADO COM OBJETOS ESPECIAIS ---
MAX_DEPTH = 16.0

def render_view_3d(surf, p):
    surf.fill((10, 10, 25))
    num_rays = surf.get_width()
    surf_h = surf.get_height()
    half_h = surf_h // 2

    pygame.draw.rect(surf, (30, 30, 30), (0, half_h, num_rays, half_h))

    fov = math.pi / 3.0
    half_fov = fov / 2.0
    delta_angle = fov / num_rays
    z_buffer = [MAX_DEPTH] * num_rays
    start_angle = p["angle"] - half_fov
    curr_wall_color = get_current_wall_color()

    for ray in range(num_rays):
        ray_angle = start_angle + ray * delta_angle
        sin_a = math.sin(ray_angle)
        cos_a = math.cos(ray_angle)

        for depth in [d * 0.05 for d in range(1, int(MAX_DEPTH * 20))]:
            target_x = p["x"] + cos_a * depth
            target_y = p["y"] + sin_a * depth

            map_x, map_y = int(target_x), int(target_y)

            if 0 <= map_x < MAP_W and 0 <= map_y < MAP_H:
                tile_val = grid_map[map_y][map_x]
                if tile_val in (1, 3):
                    corr_depth = depth * math.cos(p["angle"] - ray_angle)
                    z_buffer[ray] = corr_depth

                    proj_height = min(surf_h, int(180 / (corr_depth + 0.0001)))
                    shade = max(20, min(230, int(255 / (1 + corr_depth * corr_depth * 0.1))))

                    if tile_val == 3: # Parede Vermelha de Dano
                        wall_color = (shade, shade // 4, shade // 4)
                    else:
                        r_c, g_c, b_c = curr_wall_color
                        wall_color = (shade * r_c // 255, shade * g_c // 255, shade * b_c // 255)

                    pygame.draw.line(
                        surf, wall_color,
                        (ray, half_h - proj_height // 2),
                        (ray, half_h + proj_height // 2),
                        width=1
                    )
                    break

    sprites = []

    # 1. Pílulas
    for pel in pellets:
        dx = pel["x"] - p["x"]
        dy = pel["y"] - p["y"]
        dist = math.hypot(dx, dy)
        sprites.append({"x": pel["x"], "y": pel["y"], "dist": dist, "type": "pellet", "color": (255, 255, 180)})

    # 2. Portais de Teleporte em 3D
    ticks = pygame.time.get_ticks()
    portal_color = (180 + int(70 * math.sin(ticks * 0.01)), 50, 255)
    for tp in teleports:
        dx = tp["x"] - p["x"]
        dy = tp["y"] - p["y"]
        dist = math.hypot(dx, dy)
        sprites.append({"x": tp["x"], "y": tp["y"], "dist": dist, "type": "teleport", "color": portal_color})

    # 3. Setas Mão Única orientadas em 3D
    DIR_ANGLES = {'>': 0.0, '<': math.pi, 'v': math.pi / 2.0, '^': -math.pi / 2.0}
    for ow in one_ways:
        dx = ow["x"] - p["x"]
        dy = ow["y"] - p["y"]
        dist = math.hypot(dx, dy)
        sprites.append({"x": ow["x"], "y": ow["y"], "dist": dist, "type": "oneway", "dir_char": ow["type"], "world_angle": DIR_ANGLES[ow["type"]]})

    # 4. Fantasmas
    for g in ghosts:
        if g["respawn"] == 0:
            dx = g["x"] - p["x"]
            dy = g["y"] - p["y"]
            dist = math.hypot(dx, dy)
            g_color = (255, 255, 255) if g.get("flash", 0) > 0 else g["color"]
            sprites.append({"x": g["x"], "y": g["y"], "dist": dist, "type": "ghost", "color": g_color})

    # 5. Outro Jogador
    other_p = p2 if p == p1 else p1
    if is_coop_mode and other_p["hp"] > 0:
        dx = other_p["x"] - p["x"]
        dy = other_p["y"] - p["y"]
        dist = math.hypot(dx, dy)
        sprites.append({"x": other_p["x"], "y": other_p["y"], "dist": dist, "type": "player", "color": other_p["color"]})

    sprites.sort(key=lambda s: s["dist"], reverse=True)

    for sp in sprites:
        dx = sp["x"] - p["x"]
        dy = sp["y"] - p["y"]
        sp_angle = math.atan2(dy, dx) - p["angle"]

        while sp_angle > math.pi: sp_angle -= 2 * math.pi
        while sp_angle < -math.pi: sp_angle += 2 * math.pi

        if -half_fov - 0.2 < sp_angle < half_fov + 0.2 and sp["dist"] > 0.2:
            screen_x = int((sp_angle + half_fov) / fov * num_rays)
            size = min(surf_h, int(140 / sp["dist"]))

            ray_idx = max(0, min(num_rays - 1, screen_x))
            if sp["dist"] < z_buffer[ray_idx]:
                top_y = half_h - size // 2

                if sp["type"] == "pellet":
                    pygame.draw.circle(surf, sp["color"], (screen_x, half_h + size // 4), max(2, size // 6))

                elif sp["type"] == "teleport":  # Pilar de Portal Animado em 3D
                    p_w = max(4, size // 3)
                    pygame.draw.rect(surf, sp["color"], (screen_x - p_w // 2, top_y, p_w, size))
                    pygame.draw.ellipse(surf, (0, 255, 255), (screen_x - p_w, top_y + size // 4, p_w * 2, size // 2), width=2)

                elif sp["type"] == "oneway":  # Setas de Mão Única com Orientação em 3D
                    rel_angle = sp["world_angle"] - p["angle"]
                    while rel_angle > math.pi: rel_angle -= 2 * math.pi
                    while rel_angle < -math.pi: rel_angle += 2 * math.pi

                    s_size = max(6, size // 2)
                    cen_y = half_h + size // 4

                    # Desenhar indicador da seta conforme o ângulo relativo
                    if abs(rel_angle) < math.pi / 4.0:  # Aponta para Frente
                        pts = [(screen_x, cen_y - s_size), (screen_x - s_size, cen_y + s_size), (screen_x + s_size, cen_y + s_size)]
                    elif abs(rel_angle) > 3.0 * math.pi / 4.0:  # Aponta para Trás
                        pts = [(screen_x, cen_y + s_size), (screen_x - s_size, cen_y - s_size), (screen_x + s_size, cen_y - s_size)]
                    elif rel_angle > 0:  # Aponta para Direita
                        pts = [(screen_x + s_size, cen_y), (screen_x - s_size, cen_y - s_size), (screen_x - s_size, cen_y + s_size)]
                    else:  # Aponta para Esquerda
                        pts = [(screen_x - s_size, cen_y), (screen_x + s_size, cen_y - s_size), (screen_x + s_size, cen_y + s_size)]

                    pygame.draw.polygon(surf, (255, 220, 0), pts)
                    pygame.draw.polygon(surf, (0, 0, 0), pts, width=1)

                elif sp["type"] == "ghost":
                    pygame.draw.ellipse(surf, sp["color"], (screen_x - size // 2, top_y, size, size))
                    pygame.draw.circle(surf, (255, 255, 255), (screen_x - size // 5, top_y + size // 3), max(1, size // 8))
                    pygame.draw.circle(surf, (255, 255, 255), (screen_x + size // 5, top_y + size // 3), max(1, size // 8))

                elif sp["type"] == "player":
                    pygame.draw.rect(surf, sp["color"], (screen_x - size // 4, top_y + size // 4, size // 2, size // 1.5))
                    pygame.draw.circle(surf, (255, 220, 180), (screen_x, top_y + size // 6), size // 5)

    # DIBUJO DAS ARMAS (PISTOLA / SHOTGUN)
    w_offset_y = 12 if p["shoot_timer"] > 0 else 0
    num_rays = surf.get_width()

    if p["weapon"] == 0:  # Pistola
        gun_w = max(14, num_rays // 16)
        gun_x = (num_rays - gun_w) // 2
        pygame.draw.rect(surf, (180, 180, 190), (gun_x, surf_h - 50 + w_offset_y, gun_w, 50))
        if p["shoot_timer"] > 4:
            pygame.draw.circle(surf, (255, 220, 50), (num_rays // 2, surf_h - 55), 10)
    else:  # Shotgun
        gun_w = max(26, num_rays // 10)
        gun_x = (num_rays - gun_w) // 2
        pygame.draw.rect(surf, (110, 80, 50), (gun_x, surf_h - 65 + w_offset_y, gun_w, 65))
        pygame.draw.rect(surf, (50, 50, 50), (gun_x + 4, surf_h - 75 + w_offset_y, gun_w - 8, 20))
        if p["shoot_timer"] > 20:
            pygame.draw.circle(surf, (255, 180, 30), (num_rays // 2, surf_h - 80), 22)

    pygame.draw.circle(surf, (0, 255, 0), (num_rays // 2, half_h), 3, width=1)

# --- LOOP PRINCIPAL ---
clock = pygame.time.Clock()
running = True

while running:
    dt = clock.tick(60)
    if round_banner_timer > 0: round_banner_timer -= 1

    # 1. PROCESSAMENTO DE EVENTOS
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            update_joysticks()

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F1:
                swap_screens = not swap_screens
                play_sfx(sfx_menu)
            elif event.key == pygame.K_F2:
                rotation_angle = (rotation_angle + 90) % 360
                play_sfx(sfx_menu)
            elif event.key == pygame.K_F3:
                curr_res_idx = (curr_res_idx + 1) % len(RESOLUTIONS)
                if not is_fullscreen:
                    screen = pygame.display.set_mode(RESOLUTIONS[curr_res_idx], pygame.RESIZABLE)
                play_sfx(sfx_menu)
            elif event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode(RESOLUTIONS[curr_res_idx], pygame.RESIZABLE)
                play_sfx(sfx_menu)

            elif game_state == STATE_CUSTOMIZE:
                p_ref = p1 if cust_player == 1 else p2
                if event.key == pygame.K_RETURN:
                    p_ref["name"] = active_text_input.strip() if active_text_input.strip() else f"P{cust_player}"
                    play_sfx(sfx_menu)
                    if cust_player == 1 and is_coop_mode:
                        cust_player = 2
                        active_text_input = ""
                    else:
                        start_new_game()
                elif event.key == pygame.K_BACKSPACE:
                    active_text_input = active_text_input[:-1]
                else:
                    if len(active_text_input) < 10 and event.unicode.isalnum():
                        active_text_input += event.unicode.upper()

            elif event.key in (pygame.K_p, pygame.K_ESCAPE):
                if game_state == STATE_PLAYING: game_state = STATE_PAUSED
                elif game_state == STATE_PAUSED: game_state = STATE_PLAYING
                play_sfx(sfx_menu)

            elif event.key in (pygame.K_r, pygame.K_SPACE, pygame.K_RETURN):
                if game_state in (STATE_PAUSED, STATE_GAMEOVER):
                    game_state = STATE_MENU
                    play_sfx(sfx_menu)

            elif game_state == STATE_MENU:
                if event.key in (pygame.K_1, pygame.K_KP1):
                    is_coop_mode = False
                    cust_player = 1
                    active_text_input = ""
                    game_state = STATE_CUSTOMIZE
                    play_sfx(sfx_menu)
                elif event.key in (pygame.K_2, pygame.K_KP2):
                    is_coop_mode = True
                    cust_player = 1
                    active_text_input = ""
                    game_state = STATE_CUSTOMIZE
                    play_sfx(sfx_menu)

            elif game_state == STATE_PLAYING:
                if event.key == pygame.K_1: p1["weapon"] = 0
                elif event.key == pygame.K_2: p1["weapon"] = 1
                elif event.key in (pygame.K_z, pygame.K_SPACE): shoot_weapon(p1)

                if is_coop_mode:
                    if event.key == pygame.K_KP1: p2["weapon"] = 0
                    elif event.key == pygame.K_KP2: p2["weapon"] = 1
                    elif event.key in (pygame.K_RETURN, pygame.K_RSHIFT): shoot_weapon(p2)

        elif event.type == pygame.JOYBUTTONDOWN:
            if event.button in (6, 7):
                if game_state == STATE_PLAYING: game_state = STATE_PAUSED
                elif game_state == STATE_PAUSED: game_state = STATE_PLAYING
                elif game_state == STATE_GAMEOVER: game_state = STATE_MENU
                play_sfx(sfx_menu)

            elif game_state == STATE_GAMEOVER and event.button in (0, 1):
                game_state = STATE_MENU
                play_sfx(sfx_menu)

            elif game_state == STATE_PLAYING:
                j_id = event.joy
                p_curr = p1 if j_id == 0 else (p2 if is_coop_mode else p1)
                if event.button in (2, 3, 4, 5):
                    p_curr["weapon"] = 1 - p_curr["weapon"]
                    play_sfx(sfx_menu)

    # 2. MOVIMENTAÇÃO E FÍSICA
    if game_state == STATE_PLAYING:
        keys = pygame.key.get_pressed()
        rot_speed = 0.085
        move_speed = 0.065

        # P1
        if p1["hp"] > 0:
            dx1, dy1 = 0, 0
            if keys[pygame.K_a]: p1["angle"] -= rot_speed
            if keys[pygame.K_d]: p1["angle"] += rot_speed

            if keys[pygame.K_w]:
                dx1 += math.cos(p1["angle"]) * move_speed
                dy1 += math.sin(p1["angle"]) * move_speed
            if keys[pygame.K_s]:
                dx1 -= math.cos(p1["angle"]) * move_speed
                dy1 -= math.sin(p1["angle"]) * move_speed

            if len(joysticks) >= 1:
                j1 = joysticks[0]
                ax0, ax1 = j1.get_axis(0), j1.get_axis(1)

                rs_x1 = 0
                if j1.get_numaxes() >= 4:
                    rs_x1 = j1.get_axis(2) if abs(j1.get_axis(2)) > 0.2 else (j1.get_axis(3) if abs(j1.get_axis(3)) > 0.2 else 0)
                elif j1.get_numaxes() >= 3:
                    rs_x1 = j1.get_axis(2)

                if abs(rs_x1) > 0.2: p1["angle"] += rs_x1 * rot_speed

                if abs(ax1) > 0.2:
                    dx1 -= math.cos(p1["angle"]) * (ax1 * move_speed)
                    dy1 -= math.sin(p1["angle"]) * (ax1 * move_speed)
                if abs(ax0) > 0.2:
                    dx1 += math.cos(p1["angle"] + math.pi / 2.0) * (ax0 * move_speed)
                    dy1 += math.sin(p1["angle"] + math.pi / 2.0) * (ax0 * move_speed)

                if j1.get_button(0) or j1.get_axis(5) > 0.3: shoot_weapon(p1)

            if not check_one_way_block(p1["x"], p1["y"], dx1, dy1):
                nx1, ny1 = p1["x"] + dx1, p1["y"] + dy1
                if get_tile_type(nx1, p1["y"]) == 3 and p1["invulnerable"] == 0:
                    p1["hp"] = max(0, p1["hp"] - 10); p1["invulnerable"] = 30; play_sfx(sfx_hit)
                elif not is_wall(nx1, p1["y"]): p1["x"] = nx1

                if get_tile_type(p1["x"], ny1) == 3 and p1["invulnerable"] == 0:
                    p1["hp"] = max(0, p1["hp"] - 10); p1["invulnerable"] = 30; play_sfx(sfx_hit)
                elif not is_wall(p1["x"], ny1): p1["y"] = ny1

            check_teleport(p1)

        # P2
        if is_coop_mode and p2["hp"] > 0:
            dx2, dy2 = 0, 0
            if keys[pygame.K_LEFT]: p2["angle"] -= rot_speed
            if keys[pygame.K_RIGHT]: p2["angle"] += rot_speed

            if keys[pygame.K_UP]:
                dx2 += math.cos(p2["angle"]) * move_speed
                dy2 += math.sin(p2["angle"]) * move_speed
            if keys[pygame.K_DOWN]:
                dx2 -= math.cos(p2["angle"]) * move_speed
                dy2 -= math.sin(p2["angle"]) * move_speed

            if len(joysticks) >= 2:
                j2 = joysticks[1]
                ax0, ax1 = j2.get_axis(0), j2.get_axis(1)

                rs_x2 = 0
                if j2.get_numaxes() >= 4:
                    rs_x2 = j2.get_axis(2) if abs(j2.get_axis(2)) > 0.2 else (j2.get_axis(3) if abs(j2.get_axis(3)) > 0.2 else 0)
                elif j2.get_numaxes() >= 3:
                    rs_x2 = j2.get_axis(2)

                if abs(rs_x2) > 0.2: p2["angle"] += rs_x2 * rot_speed

                if abs(ax1) > 0.2:
                    dx2 -= math.cos(p2["angle"]) * (ax1 * move_speed)
                    dy2 -= math.sin(p2["angle"]) * (ax1 * move_speed)
                if abs(ax0) > 0.2:
                    dx2 += math.cos(p2["angle"] + math.pi / 2.0) * (ax0 * move_speed)
                    dy2 += math.sin(p2["angle"] + math.pi / 2.0) * (ax0 * move_speed)

                if j2.get_button(0) or j2.get_axis(5) > 0.3: shoot_weapon(p2)

            if not check_one_way_block(p2["x"], p2["y"], dx2, dy2):
                nx2, ny2 = p2["x"] + dx2, p2["y"] + dy2
                if get_tile_type(nx2, p2["y"]) == 3 and p2["invulnerable"] == 0:
                    p2["hp"] = max(0, p2["hp"] - 10); p2["invulnerable"] = 30; play_sfx(sfx_hit)
                elif not is_wall(nx2, p2["y"]): p2["x"] = nx2

                if get_tile_type(p2["x"], ny2) == 3 and p2["invulnerable"] == 0:
                    p2["hp"] = max(0, p2["hp"] - 10); p2["invulnerable"] = 30; play_sfx(sfx_hit)
                elif not is_wall(p2["x"], ny2): p2["y"] = ny2

            check_teleport(p2)

        if p1["shoot_timer"] > 0: p1["shoot_timer"] -= 1
        if p2["shoot_timer"] > 0: p2["shoot_timer"] -= 1
        if p1["invulnerable"] > 0: p1["invulnerable"] -= 1
        if p2["invulnerable"] > 0: p2["invulnerable"] -= 1

        for g in ghosts:
            update_ghost_ai(g)

        for p in pellets[:]:
            for p_curr in (p1, p2 if is_coop_mode else p1):
                if p_curr["hp"] > 0 and math.hypot(p["x"] - p_curr["x"], p["y"] - p_curr["y"]) < 0.55:
                    if p in pellets: pellets.remove(p)
                    p_curr["score"] += 10
                    p_curr["ammo"] = min(99, p_curr["ammo"] + 3)
                    play_sfx(sfx_pickup)

        check_clear_pellets()
        check_game_over()

    # =========================================================================
    # RENDERIZAÇÃO TELA 3D
    # =========================================================================
    if not is_coop_mode:
        render_view_3d(surf_top_3d, p1)
    else:
        surf_p1_3d = pygame.Surface((240, 250))
        surf_p2_3d = pygame.Surface((240, 250))

        if p1["hp"] > 0:
            render_view_3d(surf_p1_3d, p1)
        else:
            surf_p1_3d.fill((40, 0, 0))
            t_d1 = font_hud.render(f"{p1['name']} MORTO", True, (255, 50, 50))
            surf_p1_3d.blit(t_d1, (120 - t_d1.get_width() // 2, 110))

        if p2["hp"] > 0:
            render_view_3d(surf_p2_3d, p2)
        else:
            surf_p2_3d.fill((40, 0, 0))
            t_d2 = font_hud.render(f"{p2['name']} MORTO", True, (255, 50, 50))
            surf_p2_3d.blit(t_d2, (120 - t_d2.get_width() // 2, 110))

        surf_top_3d.blit(surf_p1_3d, (0, 0))
        surf_top_3d.blit(surf_p2_3d, (240, 0))

        pygame.draw.line(surf_top_3d, (255, 255, 0), (240, 0), (240, 250), width=3)

        lbl1 = font_hud.render(p1["name"], True, p1["color"])
        lbl2 = font_hud.render(p2["name"], True, p2["color"])
        surf_top_3d.blit(lbl1, (8, 8))
        surf_top_3d.blit(lbl2, (248, 8))

    if round_banner_timer > 0 and game_state == STATE_PLAYING:
        t_r_banner = font_large.render(f"[ ROUND {current_round} ]", True, (255, 220, 0))
        surf_top_3d.blit(t_r_banner, (240 - t_r_banner.get_width() // 2, 30))

    surf_top_scaled = pygame.transform.scale(surf_top_3d, (VIEW_W, VIEW_H))

    # =========================================================================
    # RENDERIZAÇÃO TELA 2D (RADAR)
    # =========================================================================
    surf_bottom_2d.fill((5, 5, 10))

    tile_size = 35
    off_x = (VIEW_W - (MAP_W * tile_size)) // 2
    off_y = 40
    curr_wall_color = get_current_wall_color()

    for r in range(MAP_H):
        for c in range(MAP_W):
            rx = off_x + c * tile_size
            ry = off_y + r * tile_size
            tile_val = grid_map[r][c]

            if tile_val == 1:
                pygame.draw.rect(surf_bottom_2d, curr_wall_color, (rx, ry, tile_size, tile_size), width=2, border_radius=4)
            elif tile_val == 3:
                pygame.draw.rect(surf_bottom_2d, (230, 40, 40), (rx, ry, tile_size, tile_size), border_radius=4)
            elif tile_val == 'T':
                pygame.draw.rect(surf_bottom_2d, (120, 0, 200), (rx, ry, tile_size, tile_size), border_radius=4)
                pygame.draw.circle(surf_bottom_2d, (255, 0, 255), (rx + tile_size // 2, ry + tile_size // 2), 10, width=2)
                pygame.draw.circle(surf_bottom_2d, (0, 255, 255), (rx + tile_size // 2, ry + tile_size // 2), 4)
            else:
                pygame.draw.rect(surf_bottom_2d, (15, 15, 25), (rx, ry, tile_size, tile_size))

                if tile_val == '>':
                    pygame.draw.polygon(surf_bottom_2d, (255, 220, 0), [(rx+8, ry+10), (rx+24, ry+17), (rx+8, ry+24)])
                elif tile_val == '<':
                    pygame.draw.polygon(surf_bottom_2d, (255, 220, 0), [(rx+24, ry+10), (rx+8, ry+17), (rx+24, ry+24)])
                elif tile_val == 'v':
                    pygame.draw.polygon(surf_bottom_2d, (255, 220, 0), [(rx+10, ry+8), (rx+17, ry+24), (rx+24, ry+8)])
                elif tile_val == '^':
                    pygame.draw.polygon(surf_bottom_2d, (255, 220, 0), [(rx+10, ry+24), (rx+17, ry+8), (rx+24, ry+24)])

    for p in pellets:
        px = int(off_x + p["x"] * tile_size)
        py = int(off_y + p["y"] * tile_size)
        pygame.draw.circle(surf_bottom_2d, (255, 255, 180), (px, py), 4)

    for g in ghosts:
        if g["respawn"] == 0:
            gx = int(off_x + g["x"] * tile_size)
            gy = int(off_y + g["y"] * tile_size)
            g_color = (255, 255, 255) if g.get("flash", 0) > 0 else g["color"]
            pygame.draw.circle(surf_bottom_2d, g_color, (gx, gy), 11)

    for p_curr in ([p1, p2] if is_coop_mode else [p1]):
        if p_curr["hp"] > 0:
            px_2d = off_x + p_curr["x"] * tile_size
            py_2d = off_y + p_curr["y"] * tile_size
            p_ang = p_curr["angle"]

            tip = (px_2d + math.cos(p_ang) * 16, py_2d + math.sin(p_ang) * 16)
            wing_l = (px_2d + math.cos(p_ang + 2.5) * 10, py_2d + math.sin(p_ang + 2.5) * 10)
            wing_r = (px_2d + math.cos(p_ang - 2.5) * 10, py_2d + math.sin(p_ang - 2.5) * 10)

            pygame.draw.polygon(surf_bottom_2d, p_curr["color"], [tip, wing_l, wing_r])
            pygame.draw.polygon(surf_bottom_2d, (255, 255, 255), [tip, wing_l, wing_r], width=2)

    # HUD DO JOGADOR (INCLUI NOME DA ARMA SELECIONADA)
    pygame.draw.rect(surf_bottom_2d, (20, 20, 35), (80, VIEW_H - 120, VIEW_W - 160, 85), border_radius=10)
    pygame.draw.rect(surf_bottom_2d, (255, 255, 255), (80, VIEW_H - 120, VIEW_W - 160, 85), width=3, border_radius=10)

    w_name1 = "PISTOLA" if p1["weapon"] == 0 else "SHOTGUN"
    t_rnd = font_large.render(f"ROUND: {current_round}", True, (255, 220, 0))
    t_hp1 = font_large.render(f"{p1['name']} HP: {p1['hp']}%", True, p1["color"])
    t_ammo1 = font_large.render(f"MUN: {p1['ammo']} [{w_name1}]", True, (255, 220, 0))
    t_score1 = font_large.render(f"PTS: {p1['score']}", True, (0, 255, 180))

    surf_bottom_2d.blit(t_rnd, (100, VIEW_H - 95))
    surf_bottom_2d.blit(t_hp1, (270, VIEW_H - 95))
    surf_bottom_2d.blit(t_ammo1, (480, VIEW_H - 95))
    surf_bottom_2d.blit(t_score1, (780, VIEW_H - 95))

    if is_coop_mode:
        w_name2 = "PISTOLA" if p2["weapon"] == 0 else "SHOTGUN"
        t_hp2 = font_large.render(f"{p2['name']} HP: {p2['hp']}%", True, p2["color"])
        t_ammo2 = font_large.render(f"MUN: {p2['ammo']} [{w_name2}]", True, (255, 220, 0))
        t_score2 = font_large.render(f"PTS: {p2['score']}", True, (0, 255, 180))
        surf_bottom_2d.blit(t_hp2, (980, VIEW_H - 95))
        surf_bottom_2d.blit(t_ammo2, (1190, VIEW_H - 95))
        surf_bottom_2d.blit(t_score2, (1480, VIEW_H - 95))

    # OVERLAYS
    if game_state == STATE_MENU:
        s_overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        s_overlay.fill((0, 0, 0, 230)); surf_bottom_2d.blit(s_overlay, (0, 0))

        t_m1 = font_title.render("DOOM-PAC: DUAL VOID 3D", True, (255, 50, 50))
        t_opt1 = font_large.render("[1] MODO SOLO (1 PLAYER)", True, (0, 255, 200))
        t_opt2 = font_large.render("[2] MODO CO-OP (SPLIT-SCREEN 2 PLAYERS)", True, (255, 100, 200))
        t_disp = font_hud.render(f"AJUSTES: [F1] Inverter ({'Ativo' if swap_screens else 'Padrao'}) | [F2] Rotacao ({rotation_angle}º) | [F3] Res. | [F11] Fullscreen", True, (180, 180, 180))

        surf_bottom_2d.blit(t_m1, (VIEW_W // 2 - (t_m1.get_width() // 2), VIEW_H // 2 - 240))
        surf_bottom_2d.blit(t_opt1, (VIEW_W // 2 - (t_opt1.get_width() // 2), VIEW_H // 2 - 170))
        surf_bottom_2d.blit(t_opt2, (VIEW_W // 2 - (t_opt2.get_width() // 2), VIEW_H // 2 - 120))
        surf_bottom_2d.blit(t_disp, (VIEW_W // 2 - (t_disp.get_width() // 2), VIEW_H // 2 - 60))

        t_podium_head = font_large.render("--- RANKING DE RECORDES (TOP 5) ---", True, (255, 215, 0))
        surf_bottom_2d.blit(t_podium_head, (VIEW_W // 2 - (t_podium_head.get_width() // 2), VIEW_H // 2 - 10))

        t_s_head = font_hud.render("[ MODO SOLO ]", True, (0, 255, 200))
        surf_bottom_2d.blit(t_s_head, (VIEW_W // 2 - 470, VIEW_H // 2 + 35))
        for idx, rec in enumerate(highscores.get("solo", [])[:5]):
            color = (255, 220, 0) if idx == 0 else (200, 200, 200)
            txt_entry = font_hud.render(f"{idx+1}º. {rec['name']} - {rec['score']} PTS (R{rec.get('round', 1)})", True, color)
            surf_bottom_2d.blit(txt_entry, (VIEW_W // 2 - 490, VIEW_H // 2 + 70 + (idx * 30)))

        t_c_head = font_hud.render("[ MODO CO-OP ]", True, (255, 100, 200))
        surf_bottom_2d.blit(t_c_head, (VIEW_W // 2 + 150, VIEW_H // 2 + 35))
        for idx, rec in enumerate(highscores.get("coop", [])[:5]):
            color = (255, 220, 0) if idx == 0 else (200, 200, 200)
            txt_entry = font_hud.render(f"{idx+1}º. {rec['name']} - {rec['score']} PTS (R{rec.get('round', 1)})", True, color)
            surf_bottom_2d.blit(txt_entry, (VIEW_W // 2 + 130, VIEW_H // 2 + 70 + (idx * 30)))

    elif game_state == STATE_CUSTOMIZE:
        s_overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        s_overlay.fill((0, 0, 0, 230)); surf_bottom_2d.blit(s_overlay, (0, 0))

        p_label = f"P{cust_player} ({'RED MARINE' if cust_player==1 else 'BLUE MARINE'})"
        t_c_title = font_title.render(f"DIGITE O NOME DE {p_label}:", True, (255, 255, 255))
        t_name_box = font_title.render(f"> {active_text_input}_", True, (255, 220, 0))
        t_sub = font_hud.render("Pressione ENTER para Confirmar", True, (180, 180, 180))

        surf_bottom_2d.blit(t_c_title, (VIEW_W // 2 - (t_c_title.get_width() // 2), VIEW_H // 2 - 80))
        surf_bottom_2d.blit(t_name_box, (VIEW_W // 2 - 150, VIEW_H // 2))
        surf_bottom_2d.blit(t_sub, (VIEW_W // 2 - (t_sub.get_width() // 2), VIEW_H // 2 + 80))

    elif game_state == STATE_PAUSED:
        s_overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        s_overlay.fill((0, 0, 0, 180)); surf_bottom_2d.blit(s_overlay, (0, 0))

        t_p = font_title.render("[ JOGO PAUSADO ]", True, (255, 200, 0))
        t_sub = font_large.render("Pressione 'P' / START para Continuar | 'R' / SELECT para Menu Inicial", True, (255, 255, 255))
        surf_bottom_2d.blit(t_p, (VIEW_W // 2 - (t_p.get_width() // 2), VIEW_H // 2 - 60))
        surf_bottom_2d.blit(t_sub, (VIEW_W // 2 - (t_sub.get_width() // 2), VIEW_H // 2 + 20))

    elif game_state == STATE_GAMEOVER:
        s_overlay = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
        s_overlay.fill((50, 0, 0, 200)); surf_bottom_2d.blit(s_overlay, (0, 0))

        t_go = font_title.render("[ GAME OVER ]", True, (255, 50, 50))
        t_sub = font_large.render(f"Chegou ate o ROUND {current_round}! Pressione 'R' ou START para voltar ao Menu", True, (255, 255, 255))
        surf_bottom_2d.blit(t_go, (VIEW_W // 2 - (t_go.get_width() // 2), VIEW_H // 2 - 60))
        surf_bottom_2d.blit(t_sub, (VIEW_W // 2 - (t_sub.get_width() // 2), VIEW_H // 2 + 20))

    # =========================================================================
    # COMPOSIÇÃO FINAL DAS TELAS
    # =========================================================================
    if not swap_screens:
        full_canvas.blit(surf_top_scaled, (0, 0))
        full_canvas.blit(surf_bottom_2d, (0, VIEW_H))
    else:
        full_canvas.blit(surf_bottom_2d, (0, 0))
        full_canvas.blit(surf_top_scaled, (0, VIEW_H))

    pygame.draw.line(full_canvas, (255, 255, 0), (0, VIEW_H), (VIEW_W, VIEW_H), width=6)

    if rotation_angle != 0:
        rotated_canvas = pygame.transform.rotate(full_canvas, rotation_angle)
    else:
        rotated_canvas = full_canvas

    win_w, win_h = screen.get_size()
    scaled_output = pygame.transform.smoothscale(rotated_canvas, (win_w, win_h))
    screen.blit(scaled_output, (0, 0))

    pygame.display.flip()

pygame.quit()
sys.exit()