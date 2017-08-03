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

    parser.add_option("-m","--profilematrix", dest="matrixfile", type="string",
                      help="name of profile file you want to convert")

# add common options (-h/--help, ...) and parse command line
    (options, args) = E.Start(parser, argv=argv)
    #outf = IOTools.openFile("my_output", "w")
    seen = 0
    for line in IOTools.openFile(options.matrixfile):
        #seen += 1
        #E.debug(seen)
        #if seen > 1000:
            #break
        line = line.strip()
        fields = line.split("\t")
        #print "before", len(fields)
        #for i, col in enumerate(fields):
            #if i == "":
                #fields[i] = "0"
            #else: continue

        for i, col in enumerate(fields):
            if re.match('\s',col):
                fields[i] = "0"
            else: continue

        try:
            total = sum([float(col) for col in fields[1:]])
        except ValueError:
            
            E.debug("Whole line was %s " % line) 
            E.debug("Could not convert column %s" % col)
	    raise

        if total == 0:
            continue
        else:
            for i, col in enumerate(fields):
                if i == 0: continue
                fields[i] = float(col)/total
        #print "after", len(fields)
        options.stdout.write("\t".join(map(str,fields))+"\n")
    # write footer and output benchmark information.
    E.Stop()

if __name__ == "__main__":
    sys.exit(main(sys.argv))
