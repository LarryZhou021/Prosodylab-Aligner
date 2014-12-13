# Copyright (c) 2011-2014 Kyle Gorman and Michael Wagner
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

"""
Command-line driver for the module
"""

import os
import yaml
import logging

from bisect import bisect
from shutil import copyfile

from .corpus import Corpus
from .aligner import Aligner
from .archive import Archive
from .textgrid import MLF
from .utilities import splitname, resolve_opts, \
                       ALIGNED, CONFIG, HMMDEFS, MACROS, SCORES

from argparse import ArgumentParser


LOGGING_FMT = "%(message)s"


# parse arguments
argparser = ArgumentParser(prog="align.py",
                           description="Prosodylab-Aligner")
argparser.add_argument("-c", "--configuration",
                       help="config file")
argparser.add_argument("-d", "--dictionary",
                       help="dictionary file")
argparser.add_argument("-s", "--samplerate", type=int,
                       help="analysis samplerate (in Hz)")
argparser.add_argument("-E", "--epochs", type=int,
                       help="# of epochs of training per round")
input_group = argparser.add_mutually_exclusive_group(required=True)
input_group.add_argument("-r", "--read",
                         help="read in serialized acoustic model")
input_group.add_argument("-t", "--train",
                         help="directory of data to train on")
output_group = argparser.add_mutually_exclusive_group(required=True)
output_group.add_argument("-a", "--align",
                          help="directory of data to align")
output_group.add_argument("-w", "--write",
                          help="location to write serialized model")
verbosity_group = argparser.add_mutually_exclusive_group()
verbosity_group.add_argument("-v", "--verbose", action="store_true",
                             help="Verbose output")
verbosity_group.add_argument("-V", "--extra-verbose", action="store_true",
                             help="Even more verbose output")
args = argparser.parse_args()

# set up logging
loglevel = logging.WARNING
if args.extra_verbose:
    loglevel = logging.DEBUG
elif args.verbose:
    loglevel = logging.INFO
logging.basicConfig(format=LOGGING_FMT, level=loglevel)

# input: pick one
if args.read:
    logging.info("Reading aligner from '{}'.".format(args.read))
    # warn about irrelevant flags
    if args.configuration:
        logging.warning("Ignoring config flag (-c).")
        args.configuration = None
    if args.samplerate:
        logging.warning("Ignoring samplerate flag (-s).")
        args.samplerate = None
    # create archive from -r argument
    archive = Archive(args.read)
    # read configuration file therefrom, and resolve options with it
    args.configuration = os.path.join(archive.dirname, CONFIG)
    opts = resolve_opts(args)
    # initialize aligner and set it to point to the archive data 
    aligner = Aligner(opts)
    aligner.curdir = archive.dirname
elif args.train:
    logging.info("Preparing corpus '{}'.".format(args.train))
    opts = resolve_opts(args)
    corpus = Corpus(args.train, opts)
    logging.info("Preparing aligner.")
    aligner = Aligner(opts)
    logging.info("Training aligner on corpus '{}'.".format(args.train))
    aligner.HTKbook_training_regime(corpus, opts["epochs"])
# else unreachable

# output: pick one
if args.align:
    # check to make sure we're not aligning on the training data
    if (not args.train) or (os.path.realpath(args.train) != 
                            os.path.realpath(args.align)):
        logging.info("Preparing corpus '{}'.".format(args.align))
        corpus = Corpus(args.align, opts)
    logging.info("Aligning corpus '{}'.".format(args.align))
    aligner.align_and_score(corpus, ALIGNED, SCORES)
    logging.info("Writing likelihood scores to '{}'.".format(SCORES))
    logging.info("Writing TextGrids.")
    size = MLF(ALIGNED).write(args.align)
    if not size:
        logging.error("No paths found!")
        exit(1)
    logging.debug("Wrote {} TextGrids.".format(size))
elif args.write:
    # create and populate archive
    (_, basename, _) = splitname(args.write)
    archive = Archive.empty(basename)
    archive.add(os.path.join(aligner.curdir, HMMDEFS))
    archive.add(os.path.join(aligner.curdir, MACROS))
    # whatever this is, it's not going to work once you move the data
    if "dictionary" in opts:
        del opts["dictionary"]
    with open(os.path.join(archive.dirname, CONFIG), "w") as sink:
        yaml.dump(opts, sink)
    (basename, _) = os.path.splitext(args.write)
    archive_path = os.path.relpath(archive.dump(basename))
    logging.info("Wrote aligner to '{}'.".format(archive_path))
# else unreachable

logging.info("Success!")
