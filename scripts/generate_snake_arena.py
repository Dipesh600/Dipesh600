#!/usr/bin/env python3

import argparse
import random
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


GRID_W = 42
GRID_H = 13
CELL = 20
HEADER = 48
WIDTH = GRID_W * CELL
HEIGHT = HEADER + GRID_H * CELL
BACKGROUND = "#0d1117"
PANEL = "#161b22"
GRID = "#21262d"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
FOOD = "#f2cc60"


def font(size, bold=False):
    names = [
        "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


FONT = font(12)
BOLD = font(13, True)


class Snake:
    def __init__(self, name, color, start, direction):
        self.name = name
        self.color = color
        self.start = start
        self.start_direction = direction
        self.body = deque()
        self.direction = direction
        self.score = 0
        self.best = 0
        self.resets = 0
        self.reset(set())

    def reset(self, occupied):
        x, y = self.start
        dx, dy = self.start_direction
        candidate = [(x - dx * i, y - dy * i) for i in range(3)]
        if any(cell in occupied or not in_bounds(cell) for cell in candidate):
            free = [(gx, gy) for gy in range(GRID_H) for gx in range(GRID_W) if (gx, gy) not in occupied]
            x, y = random.choice(free)
            candidate = [(x, y)]
        self.body = deque(candidate)
        self.direction = self.start_direction
        self.score = 0
        self.resets += 1


def in_bounds(cell):
    x, y = cell
    return 0 <= x < GRID_W and 0 <= y < GRID_H


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def nearest_distance(cell, rewards):
    return min(abs(cell[0] - rx) + abs(cell[1] - ry) for rx, ry in rewards)


def choose_direction(snake, rewards, occupied):
    directions = [(1, 0), (0, 1), (-1, 0), (0, -1)]
    reverse = (-snake.direction[0], -snake.direction[1])
    candidates = []
    for direction in directions:
        if direction == reverse and len(snake.body) > 1:
            continue
        head = add(snake.body[0], direction)
        if not in_bounds(head):
            continue
        danger = 1000 if head in occupied and head != snake.body[-1] else 0
        wall_risk = 2 if head[0] in (0, GRID_W - 1) or head[1] in (0, GRID_H - 1) else 0
        distance = nearest_distance(head, rewards)
        jitter = random.random() * 1.8
        candidates.append((danger + wall_risk + distance + jitter, direction))

    if not candidates:
        return snake.direction

    candidates.sort(key=lambda item: item[0])
    # Occasional imperfect decision keeps the match alive and allows real crashes.
    if len(candidates) > 1 and random.random() < 0.10:
        return random.choice(candidates[: min(3, len(candidates))])[1]
    return candidates[0][1]


def spawn_reward(rewards, occupied):
    free = [
        (x, y)
        for y in range(GRID_H)
        for x in range(GRID_W)
        if (x, y) not in occupied and (x, y) not in rewards
    ]
    if free:
        rewards.add(random.choice(free))


def color_with_alpha(hex_color, factor):
    value = hex_color.lstrip("#")
    rgb = tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    return tuple(int(channel * factor) for channel in rgb)


def draw_frame(snakes, rewards, tick, events):
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, WIDTH, HEADER - 1), fill=PANEL)
    draw.line((0, HEADER - 1, WIDTH, HEADER - 1), fill="#30363d", width=1)

    segment_width = WIDTH // len(snakes)
    for index, snake in enumerate(snakes):
        x = 16 + index * segment_width
        draw.ellipse((x, 14, x + 12, 26), fill=snake.color)
        draw.text((x + 20, 10), snake.name, font=BOLD, fill=TEXT)
        draw.text((x + 20, 27), f"score {snake.score:02d}  best {snake.best:02d}  resets {max(0, snake.resets - 1):02d}", font=FONT, fill=MUTED)

    for gx in range(GRID_W + 1):
        x = gx * CELL
        draw.line((x, HEADER, x, HEIGHT), fill=GRID, width=1)
    for gy in range(GRID_H + 1):
        y = HEADER + gy * CELL
        draw.line((0, y, WIDTH, y), fill=GRID, width=1)

    pulse = 2 if tick % 8 < 4 else 0
    for rx, ry in rewards:
        left = rx * CELL + 5 - pulse
        top = HEADER + ry * CELL + 5 - pulse
        right = (rx + 1) * CELL - 5 + pulse
        bottom = HEADER + (ry + 1) * CELL - 5 + pulse
        draw.rounded_rectangle((left, top, right, bottom), radius=3, fill=FOOD)
        draw.rectangle((rx * CELL + 9, HEADER + ry * CELL + 7, rx * CELL + 11, HEADER + ry * CELL + 13), fill="#fff8c5")
        draw.rectangle((rx * CELL + 7, HEADER + ry * CELL + 9, rx * CELL + 13, HEADER + ry * CELL + 11), fill="#fff8c5")

    for snake in snakes:
        body_len = max(1, len(snake.body))
        for index, (sx, sy) in enumerate(reversed(snake.body)):
            progress = (index + 1) / body_len
            fill = color_with_alpha(snake.color, 0.45 + progress * 0.55)
            padding = 3 if index < body_len - 1 else 2
            box = (
                sx * CELL + padding,
                HEADER + sy * CELL + padding,
                (sx + 1) * CELL - padding,
                HEADER + (sy + 1) * CELL - padding,
            )
            draw.rounded_rectangle(box, radius=5, fill=fill)

        hx, hy = snake.body[0]
        cx = hx * CELL + CELL // 2
        cy = HEADER + hy * CELL + CELL // 2
        dx, dy = snake.direction
        eye_x = cx + dx * 4
        eye_y = cy + dy * 4
        draw.ellipse((eye_x - 2, eye_y - 2, eye_x + 2, eye_y + 2), fill="#ffffff")

    for event in events:
        if event[0] == "reset":
            _, position, color = event
            x, y = position
            cx = x * CELL + CELL // 2
            cy = HEADER + y * CELL + CELL // 2
            draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), outline=color, width=2)

    return image


def simulate(frame_count, seed):
    random.seed(seed)
    snakes = [
        Snake("BLUE", "#58a6ff", (5, 3), (1, 0)),
        Snake("ORANGE", "#f0883e", (GRID_W - 6, 6), (-1, 0)),
        Snake("GREEN", "#3fb950", (7, GRID_H - 3), (1, 0)),
    ]
    rewards = set()
    occupied = {cell for snake in snakes for cell in snake.body}
    for _ in range(6):
        spawn_reward(rewards, occupied)

    frames = []
    for tick in range(frame_count):
        occupied = {cell for snake in snakes for cell in snake.body}
        proposals = {}
        for snake in snakes:
            snake.direction = choose_direction(snake, rewards, occupied)
            proposals[snake] = add(snake.body[0], snake.direction)

        collisions = set()
        proposed_cells = list(proposals.values())
        for snake, new_head in proposals.items():
            if not in_bounds(new_head):
                collisions.add(snake)
                continue
            others = occupied - {snake.body[-1]}
            if new_head in others:
                collisions.add(snake)
            if proposed_cells.count(new_head) > 1:
                collisions.add(snake)
            for other in snakes:
                if other is not snake and new_head == other.body[0] and proposals.get(other) == snake.body[0]:
                    collisions.add(snake)

        events = []
        eaten = set()
        for snake in snakes:
            if snake in collisions:
                crash_at = proposals[snake]
                remaining = {cell for other in snakes if other is not snake for cell in other.body}
                snake.reset(remaining)
                events.append(("reset", crash_at, snake.color))
                continue

            new_head = proposals[snake]
            snake.body.appendleft(new_head)
            if new_head in rewards:
                eaten.add(new_head)
                snake.score += 1
                snake.best = max(snake.best, snake.score)
            else:
                snake.body.pop()

        rewards -= eaten
        occupied = {cell for snake in snakes for cell in snake.body}
        while len(rewards) < 6:
            spawn_reward(rewards, occupied)

        frames.append(draw_frame(snakes, rewards, tick, events))

    return frames


def main():
    parser = argparse.ArgumentParser(description="Generate an autonomous multi-snake arena GIF.")
    parser.add_argument("--output", default="output/snake-arena.gif")
    parser.add_argument("--frames", type=int, default=220)
    parser.add_argument("--seed", type=int, default=20260718)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frames = simulate(args.frames, args.seed)
    palette_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for frame in frames]
    palette_frames[0].save(
        output,
        save_all=True,
        append_images=palette_frames[1:],
        duration=85,
        loop=0,
        disposal=2,
        optimize=False,
    )
    print(f"Generated {output} with {len(frames)} frames (seed={args.seed}).")


if __name__ == "__main__":
    main()
