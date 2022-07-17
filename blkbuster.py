#!/usr/bin/python3

import sys
import re
import collections
import numpy
import PIL
import PIL.Image
import PIL.ImageDraw
from moviepy.video.VideoClip import VideoClip, DataVideoClip

# blkparse line with a Q entry (queued) and RWD (read/write/discard) op
line_re = re.compile(r'^[\d,]+\s+\d+\s+\d+\s+([\d\.]+)\s+\d+\s+Q\s+([RWD])S?M?\s+(\d+) \+ (\d+).*')

io = collections.namedtuple('io', ('offset', 'size', 'direction'))
frames = [[]] # of array of io

frame_rate = 60

frame_time = 1 / frame_rate

max_offset = 0

width = 3840
height = 2160

inset_width = width * 8 // 10
inset_height = height * 8 // 10
inset_col = width // 10
inset_row = height // 10

time = 0.0
next_frame = time + frame_time
for line in sys.stdin.readlines():
    m = re.match(line_re, line)
    if not m:
        continue
    time, direction, offset, size = m.groups()
    time = float(time)
    offset = int(offset)
    size = int(size)
    this_io = io(offset, size, direction)
    while time >= next_frame:
        frames.append([])
        next_frame += frame_time
    frames[-1].append(this_io)
    max_offset = max(max_offset, offset + size)

def row_col(offset):
    frac_row = inset_row + offset / max_offset * inset_height
    row = int(frac_row)
    col = inset_col + int((frac_row - row) * inset_width) 
    return row, col

direction_color = {
    'R': 'green',
    'W': 'blue',
    'D': 'red',
}

def make_frame(frame):
    img = PIL.Image.new(mode='RGB', size=(width, height), color='white')
    # f = numpy.full(shape=(height, width, 3), fill_value=255, dtype=numpy.uint8)
    draw = PIL.ImageDraw.Draw(img)
    for io in frame:
        r1, c1 = row_col(io.offset)
        r2, c2 = row_col(io.offset + io.size - 1)
        fill=direction_color[io.direction]
        while r1 != r2:
            draw.line([(c1, r1), (inset_width-1, r1)], fill=fill, width=3)
            r1 += 1
            c1 = inset_col
        draw.line([(c1, r1), (c2, r2)], fill=fill, width=3)
    return numpy.asarray(img)

clip = DataVideoClip(frames, make_frame, fps=frame_rate)

clip.write_videofile('blkbuster.avi', codec='libx264', audio=False)
