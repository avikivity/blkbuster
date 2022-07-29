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

argparser = argparse.ArgumentParser(prog='blkbuster',
                                    description='Convert blkparse output to funky videos')
argparser.add_argument('-r', '--frame-rate', metavar='FPS', type=int, default=60)
argparser.add_argument('-x', '--width', metavar='PIXELS', type=int, default=3840)
argparser.add_argument('-y', '--height', metavar='PIXELS', type=int, default=2160)
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

direction_color = {k: PIL.ImageColor.getrgb(direction_color[k]) for k in direction_color}

white = PIL.ImageColor.getrgb('white')

def blend(intensity, c1, c2):
    def blend_component(n):
        return int(intensity*c1[n] + (1-intensity)*c2[2])
    return (blend_component(0), blend_component(1), blend_component(2))

def make_frame(t):
    start_time = t - (fade_window_time + frame_time)
    end_time = t
    img = PIL.Image.new(mode='RGB', size=(width, height), color='white')
    # f = numpy.full(shape=(height, width, 3), fill_value=255, dtype=numpy.uint8)
    draw = PIL.ImageDraw.Draw(img)
    left_bound = bisect.bisect_right(timeline, start_time, key=lambda io: io.time)
    right_bound = bisect.bisect_right(timeline, end_time, key=lambda io: io.time)
    rd = io_radius
    for io in timeline[left_bound:right_bound]:
        r1, c1 = row_col(io.offset)
        r2, c2 = row_col(io.offset + io.size - 1)
        intensity = math.exp(-(t - io.time) / fade_decay_time)
        fill = blend(intensity, direction_color[io.direction], white)
        while r1 != r2:
            draw.rounded_rectangle([(c1-rd, r1-rd), (inset_col + inset_width-1+rd, r1+rd)], fill=fill, radius=rd)
            r1 += 1
            c1 = inset_col
        draw.rounded_rectangle([(c1-rd, r1-rd), (c2+rd, r2+rd)], fill=fill, radius=rd)
    return numpy.asarray(img)

clip = VideoClip(make_frame, duration=timeline[-1].time)

clip.write_videofile(args.output, codec='libx264', fps=frame_rate, audio=False)
