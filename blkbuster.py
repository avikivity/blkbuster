#!/usr/bin/python3

import sys
import re
import collections
import numpy
import math
import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageColor
from moviepy.video.VideoClip import VideoClip, DataVideoClip
import bisect
import argparse

themes = {
    'light': {
        'R': 'green',
        'W': 'blue',
        'D': 'red',
        'BG': 'white',
    },
    'dark': {
        'R': '#00ff21',
        'W': '#7f92ff',
        'D': '#ff7f7f',
        'BG': '#121212',
    }
}

argparser = argparse.ArgumentParser(prog='blkbuster',
                                    description='Convert blkparse output to funky videos')
argparser.add_argument('-r', '--frame-rate', metavar='FPS', type=int, default=60)
argparser.add_argument('-x', '--width', metavar='PIXELS', type=int, default=3840)
argparser.add_argument('-y', '--height', metavar='PIXELS', type=int, default=2160)
argparser.add_argument('-s', '--stripes', metavar='STRIPES', type=int, default=500,
                       help='how many stripes to divide the display into')
argparser.add_argument('--theme', metavar='NAME', choices=themes.keys(), default='light',
                       help=f'Color theme selection {list(themes.keys())}')
argparser.add_argument('input', metavar='INPUT',
                       help='Input file (blkparse output)')
argparser.add_argument('output', metavar='OUTPUT',
                       help='Output file (video clip)')

args = argparser.parse_args()

# blkparse line with a Q entry (queued) and RWD (read/write/discard) op
line_re = re.compile(r'^[\d,]+\s+\d+\s+\d+\s+([\d\.]+)\s+\d+\s+Q\s+([RWD])S?M?\s+(\d+) \+ (\d+).*')

io = collections.namedtuple('io', ('time', 'offset', 'size', 'direction'))
timeline = [] # of array of io

frame_rate = args.frame_rate

frame_time = 1 / frame_rate

max_offset = 0

fade_decay_time = 0.08
fade_window_time = 0.5

width = args.width
height = args.height

logical_height = args.stripes
logical_width = logical_height * width/height

inset_width = width * 8 // 10
inset_height = height * 8 // 10
inset_col = width // 10
inset_row = height // 10


io_radius = int(math.ceil(width/1000))

time = 0.0
next_frame = time + frame_time
for line in open(args.input).readlines():
    m = re.match(line_re, line)
    if not m:
        continue
    time, direction, offset, size = m.groups()
    time = float(time)
    offset = int(offset)
    size = int(size)
    this_io = io(time, offset, size, direction)
    timeline.append(this_io)
    max_offset = max(max_offset, offset + size)

timeline.sort(key=lambda io: io.time)

def logical_row_col(offset):
    frac_row = offset / max_offset * logical_height
    row = int(frac_row)
    col = (frac_row - row) * logical_width
    return row, col

def logical_to_screen(lrow, lcol):
    return (int(inset_row + inset_height * lrow/logical_height),
            int(inset_col + inset_width * lcol/logical_width))

theme = themes[args.theme]
direction_color = theme

direction_color = {k: PIL.ImageColor.getrgb(direction_color[k]) for k in direction_color}

background = direction_color['BG']

def blend(intensity, c1, c2):
    def blend_component(n):
        return int(intensity*c1[n] + (1-intensity)*c2[2])
    return (blend_component(0), blend_component(1), blend_component(2))

def make_frame(t):
    start_time = t - (fade_window_time + frame_time)
    end_time = t
    img = PIL.Image.new(mode='RGB', size=(width, height), color=background)
    # f = numpy.full(shape=(height, width, 3), fill_value=255, dtype=numpy.uint8)
    draw = PIL.ImageDraw.Draw(img)
    left_bound = bisect.bisect_right(timeline, start_time, key=lambda io: io.time)
    right_bound = bisect.bisect_right(timeline, end_time, key=lambda io: io.time)
    rd = io_radius
    for io in timeline[left_bound:right_bound]:
        r1, c1 = logical_row_col(io.offset)
        r2, c2 = logical_row_col(io.offset + io.size - 1)
        intensity = math.exp(-(t - io.time) / fade_decay_time)
        fill = blend(intensity, direction_color[io.direction], background)
        while r1 != r2:
            sr1, sc1 = logical_to_screen(r1, c1)
            draw.rounded_rectangle([(sc1-rd, sr1-rd), (inset_col + inset_width-1+rd, sr1+rd)], fill=fill, radius=rd)
            r1 += 1
            c1 = 0
        sr1, sc1 = logical_to_screen(r1, c1)
        sr2, sc2 = logical_to_screen(r2, c2)
        draw.rounded_rectangle([(sc1-rd, sr1-rd), (sc2+rd, sr2+rd)], fill=fill, radius=rd)
    return numpy.asarray(img)

clip = VideoClip(make_frame, duration=timeline[-1].time)

clip.write_videofile(args.output, codec='libx264', fps=frame_rate, audio=False)
