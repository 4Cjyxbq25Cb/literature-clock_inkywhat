#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import random
import logging
import time
import json
from datetime import datetime
from PIL import Image, ImageFont, ImageDraw
from inky import InkyWHAT

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

large_quote_font_size  = 36
medium_quote_font_size = 28
small_quote_font_size  = 20
min_quote_font_size    = 14
base_author_font_size  = 14
line_spacing           = 6
max_display_width      = 400
max_display_height     = 280

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


class QuoteDisplay:
    """Displays literary quotes on an InkyWHAT e-ink screen.

    Each minute a random quote for that time is shown. The time portion
    of the quote is always rendered in red; the surrounding text in black.
    Font size is reduced automatically so that every quote fits on screen.
    """

    inky_display = InkyWHAT('red')  # colour variant: 'red' or 'yellow'

    def __init__(self, fixedTime=''):
        self.fixedTime  = fixedTime
        self.currentMin = -1
        self.quote_data = {}
        self.loadData()
        self.update_display()

    # ── Data loading ───────────────────────────────────────────────────────

    def loadData(self):
        """Load all per-minute quote JSON files into memory."""
        self.quote_data = {}
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'docs', 'times')
        for h in range(24):
            for m in range(60):
                key  = f'{h:02d}_{m:02d}'
                path = os.path.join(base, f'{key}.json')
                if os.path.exists(path):
                    try:
                        with open(path, encoding='utf-8') as f:
                            self.quote_data[key] = json.load(f)
                    except Exception as e:
                        log.error(f'Cannot load {path}: {e}')

    def get_quote(self, time_str):
        """Return a random quote dict for the given HH_MM key."""
        if time_str in self.quote_data:
            return random.choice(self.quote_data[time_str])
        return {
            'quote_first':     '',
            'quote_time_case': time_str.replace('_', ':'),
            'quote_last':      '',
            'title':           'N/A',
            'author':          'N/A',
        }

    # ── Text layout ────────────────────────────────────────────────────────

    def word_parts(self, first, time_str, last):
        """Split all three quote segments into (word, part) tuples.

        part is one of 'first', 'time', or 'last', used to pick the
        correct ink color when drawing.
        """
        result = []
        for w in first.split():
            result.append((w, 'first'))
        for w in time_str.split():
            result.append((w, 'time'))
        for w in last.split():
            result.append((w, 'last'))
        return result

    def wrap(self, word_parts, font, max_width):
        """Wrap word_parts into display lines, preserving per-word part info."""
        lines, line, w = [], [], 0
        sp = font.getbbox(' ')[2]
        for word, part in word_parts:
            ww  = font.getbbox(word)[2]
            gap = sp if line else 0
            if line and w + gap + ww > max_width:
                lines.append(line)
                line, w = [(word, part)], ww
            else:
                line.append((word, part))
                w += gap + ww
        if line:
            lines.append(line)
        return lines

    def line_width(self, line, font):
        sp = font.getbbox(' ')[2]
        return sum(font.getbbox(w)[2] for w, _ in line) + sp * (len(line) - 1)

    # ── Display update loop ────────────────────────────────────────────────

    def update_display(self):
        """Main loop: refresh the display once per minute."""
        while True:
            now = datetime.now()
            key = now.strftime('%H_%M')

            if now.minute != self.currentMin:
                self.currentMin = now.minute
                log.debug(f'Updating display for {key}')

                q     = self.get_quote(key if not self.fixedTime else self.fixedTime)
                clean = lambda s: s.replace('<br/>', ' ').replace('<br>', ' ')
                first = clean(q['quote_first'])
                ttime = q['quote_time_case'].strip()
                last  = clean(q['quote_last'])
                full  = f'{first} {ttime} {last}'.strip()

                # Choose starting font size by quote length; shrink until it fits
                if   len(full) < 100: font_size = large_quote_font_size
                elif len(full) < 200: font_size = medium_quote_font_size
                else:                 font_size = small_quote_font_size

                while font_size >= min_quote_font_size:
                    font   = ImageFont.truetype(FONT, font_size)
                    parts  = self.word_parts(first, ttime, last)
                    lines  = self.wrap(parts, font, max_display_width)
                    height = len(lines) * (font_size + line_spacing) - line_spacing
                    if height <= max_display_height:
                        break
                    font_size -= 2

                img  = Image.new('P', (400, 300), self.inky_display.WHITE)
                draw = ImageDraw.Draw(img)
                sp   = font.getbbox(' ')[2]
                y    = (max_display_height - height) // 2

                for line in lines:
                    x = max((max_display_width - self.line_width(line, font)) // 2, 0)
                    for i, (word, part) in enumerate(line):
                        color = self.inky_display.RED if part == 'time' else self.inky_display.BLACK
                        draw.text((x, y), word, fill=color, font=font)
                        x += font.getbbox(word)[2]
                        if i < len(line) - 1:
                            x += sp
                    y += font_size + line_spacing

                author = f"{q['title']} – {q['author']}"
                afont  = ImageFont.truetype(FONT, base_author_font_size)
                ah     = draw.textbbox((0, 0), author, font=afont)[3]
                draw.text((10, 300 - ah - 10), author, fill=self.inky_display.BLACK, font=afont)

                img = img.rotate(180, expand=True)
                self.inky_display.set_image(img)
                self.inky_display.show()

            time.sleep(60)


if __name__ == '__main__':
    QuoteDisplay()
