
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re
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
    inky_display = InkyWHAT('red')

    def __init__(self, fixedTime=''):
        self.fixedTime   = fixedTime
        self.currentMin  = -1
        self.quote_data  = {}
        self.loadData()
        self.update_display()

    def loadData(self):
        self.quote_data = {}
        base = os.path.join(os.path.dirname(__file__), 'docs/times')
        for h in range(24):
            for m in range(60):
                key  = f'{h:02d}_{m:02d}'
                path = f'{base}/{key}.json'
                if os.path.exists(path):
                    try:
                        with open(path) as f:
                            self.quote_data[key] = json.load(f)
                    except Exception as e:
                        log.error(f'Cannot load {path}: {e}')

    def get_quote(self, time_str):
        if time_str in self.quote_data:
            return random.choice(self.quote_data[time_str])
        return {
            'quote_first': '', 'quote_time_case': time_str.replace('_', ':'),
            'quote_last': '', 'title': 'N/A', 'author': 'N/A'
        }

    # ── Kürzung langer Zitate ──────────────────────────────────────────────

    MAX_CHARS = 150

    # Abkürzungen die nicht als Satzende gelten
    _ABBREVS = re.compile(
        r'\b(Mr|Mrs|Ms|Dr|Prof|St|vs|etc|al|Jr|Sr|Rev|Gen|Lt|Sgt|Cpt|Ltd|Inc|Co|Fig|No|Vol|pp|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.',
        re.IGNORECASE
    )

    def split_sentences(self, text):
        # Abkürzungsperioden temporär schützen
        protected = self._ABBREVS.sub(r'\1<DOT>', text)
        parts = re.split(r'(?<=[.!?])\s+|(?<=[.!?]["\'])\s+', protected.strip())
        # Schutz rückgängig machen
        parts = [p.replace('<DOT>', '.').strip() for p in parts]
        return [p for p in parts if len(p) > 2]

    def trim_quote(self, first, ttime, last):
        def length(f, l):
            return len(f'{f} {ttime} {l}'.strip())

        if length(first, last) <= self.MAX_CHARS:
            return first, last

        first_sents = self.split_sentences(first)
        last_sents  = self.split_sentences(last)

        # Kernprinzip: nur den Satz behalten, der direkt an die Uhrzeit grenzt.
        # first_sents[-1] führt direkt in ttime, last_sents[0] folgt direkt darauf.
        core_first = first_sents[-1] if first_sents else ''
        core_last  = last_sents[0]   if last_sents  else ''

        # Versuch 1: Kernsätze beiderseits
        if length(core_first, core_last) <= self.MAX_CHARS:
            return core_first, core_last

        # Versuch 2: nur Kernsatz vor der Zeit
        if core_first and length(core_first, '') <= self.MAX_CHARS:
            return core_first, ''

        # Versuch 3: nur Kernsatz nach der Zeit
        if core_last and length('', core_last) <= self.MAX_CHARS:
            return '', core_last

        # Fallback: original (Display verkleinert die Schrift)
        return first, last

    # ── Text-Layout ────────────────────────────────────────────────────────

    def word_parts(self, first, time_str, last):
        """Return list of (word, part) where part is 'first'|'time'|'last'."""
        result = []
        for w in first.split():
            result.append((w, 'first'))
        for w in time_str.split():
            result.append((w, 'time'))
        for w in last.split():
            result.append((w, 'last'))
        return result

    def wrap(self, word_parts, font, max_width):
        """Wrap into lines; each line is a list of (word, part)."""
        lines, line, w = [], [], 0
        sp = font.getbbox(' ')[2]
        for word, part in word_parts:
            ww = font.getbbox(word)[2]
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

    # ── Display-Update ─────────────────────────────────────────────────────

    def update_display(self):
        while True:
            now = datetime.now()
            key = now.strftime('%H_%M')

            if now.minute != self.currentMin:
                self.currentMin = now.minute
                q = self.get_quote(key if not self.fixedTime else self.fixedTime)

                clean = lambda s: s.replace('<br/>', ' ').replace('<br>', ' ')
                first = clean(q['quote_first'])
                ttime = q['quote_time_case'].strip()
                last  = clean(q['quote_last'])
                first, last = self.trim_quote(first, ttime, last)
                full  = f'{first} {ttime} {last}'.strip()

                # Autorbereich vorab berechnen um verfügbare Quote-Höhe zu kennen
                author = f"{q['title']} – {q['author']}"
                afont  = ImageFont.truetype(FONT, base_author_font_size)
                abb    = afont.getbbox(author)
                aw, ah = abb[2], abb[3]
                ax         = max((max_display_width - aw) // 2, 0)
                author_top = 300 - ah - 10
                quote_area = author_top - 14  # 14px Mindestabstand über Autor

                # Schriftgröße wählen; verkleinern bis Text in quote_area passt
                if   len(full) < 100: font_size = large_quote_font_size
                elif len(full) < 200: font_size = medium_quote_font_size
                else:                 font_size = small_quote_font_size

                while font_size >= min_quote_font_size:
                    font   = ImageFont.truetype(FONT, font_size)
                    parts  = self.word_parts(first, ttime, last)
                    lines  = self.wrap(parts, font, max_display_width)
                    height = len(lines) * (font_size + line_spacing) - line_spacing
                    if height <= quote_area:
                        break
                    font_size -= 2

                img  = Image.new('P', (400, 300), self.inky_display.WHITE)
                draw = ImageDraw.Draw(img)
                sp   = font.getbbox(' ')[2]
                y    = max((quote_area - height) // 2, 0)

                for line in lines:
                    x = max((max_display_width - self.line_width(line, font)) // 2, 0)
                    for i, (word, part) in enumerate(line):
                        color = self.inky_display.RED if part == 'time' else self.inky_display.BLACK
                        draw.text((x, y), word, fill=color, font=font)
                        x += font.getbbox(word)[2]
                        if i < len(line) - 1:
                            x += sp
                    y += font_size + line_spacing

                draw.text((ax, author_top), author, fill=self.inky_display.BLACK, font=afont)

                img = img.rotate(180, expand=True)
                self.inky_display.set_image(img)
                self.inky_display.show()

            time.sleep(60)

if __name__ == '__main__':
    QuoteDisplay()
