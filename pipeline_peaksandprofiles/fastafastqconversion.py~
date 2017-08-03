'''
cgat_script_template.py - template for CGAT scripts
====================================================

:Author:
:Release: $Id$
:Date: |today|
:Tags: Python

Purpose
-------

.. Overall purpose and function of the script>

Usage
-----

.. Example use case

Example::

   python cgat_script_template.py

Type::

   python cgat_script_template.py --help

for command line help.

Command line options
--------------------

'''

import sys
import CGAT.Experiment as E
import os
import re
from CGAT import IOTools
from CGAT import Fastq
from CGAT import FastaIterator
def main(argv=None):
    """script main.
    parses command line options in sys.argv, unless *argv* is given.
    """

    if argv is None:
        argv = sys.argv

    # setup command line parser
    parser = E.OptionParser(version="%prog version: $Id$",
                            usage=globals()["__doc__"])

    parser.add_option("-pm","--profilematrix", dest="matrixfile", type="string",
                      help="name of profile file you want to convert")

# add common options (-h/--help, ...) and parse command line
    (options, args) = E.Start(parser, argv=argv)
    #outf = IOTools.openFile("my_output", "w")
    for line in options.matrixfile:
        line = line.strip()
        fields = line.split()
        total = sum([float(col) for col in fields[1:]])
        if total == 0:
            continue
        else:
            for i, col in enumerate(fields):
                if i == 0: continue
                fields[i] = col/total
    options.stdout.write("\t".join(map(str,fields)))
 


    for fasta_read in FastaIterator.iterate(IOTools.openFile(options.fastafile)):
	read_sequence = fasta_read.sequence
        read_name = fasta_read.title
        quals = '.' * len(read_sequence)
        
        new_fastq = Fastq.Record(identifier=read_name,
                                 seq=read_sequence,
                                 quals=quals)
        new_fastq.fromPhred([30]*len(read_sequence), format='illumina-1.8')
	options.stdout.write(str(new_fastq)+"\n")
    # write footer and output benchmark information.
    E.Stop()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
