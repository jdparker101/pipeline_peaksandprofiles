##############################################################################
#
#   MRC FGU CGAT
#
#   $Id$
#
#   Copyright (C) 2009 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
###############################################################################
"""===========================
Pipeline template
===========================

:Author: Jacob Parker
:Release: $Id$
:Date: |today|
:Tags: Python

This pipeline calculates the number of mismatches per base for a given set of genes for mapped RNA-seq data using pysam.
The data are merged into one final table.

Overview
========

files :file:``pipeline.ini` and :file:`conf.py`.

Usage
=====

See :ref:`PipelineSettingUp` and :ref:`PipelineRunning` on general
information how to use CGAT pipelines.

Configuration
-------------

The pipeline requires a configured :file:`pipeline.ini` file.
CGATReport report requires a :file:`conf.py` and optionally a
:file:`cgatreport.ini` file (see :ref:`PipelineReporting`).

Default configuration files can be generated by executing:

   python <srcdir>/pipeline_mismatch.py config

Input files
-----------

Set of genes, as specified in the `pipeline.ini` file (job:gene_list).

Requirements
------------

The pipeline requires the results from
:doc:`pipeline_annotations`. Set the configuration variable
:py:data:`annotations_database` and :py:data:`annotations_dir`.

On top of the default CGAT setup, the pipeline requires the following
software to be in the path:

.. Add any additional external requirements such as 3rd party software
   or R modules below:

Requirements:

* samtools >= 1.1

Pipeline output
===============

.. Describe output files of the pipeline here

Glossary
========

.. glossary::


Code
====

"""
from ruffus import *

import sys
import os
import sqlite3
import CGAT.Experiment as E
import CGATPipelines.Pipeline as P
import re
from CGAT import GTF
from CGAT import IOTools
# load options from the config file
PARAMS = P.getParameters(
    ["%s/pipeline.ini" % os.path.splitext(__file__)[0],
     "../pipeline.ini",
     "pipeline.ini"])

PARAMS["pipelinedir"] = os.path.dirname(__file__)


# ---------------------------------------------------
# Specific pipeline tasks
#Files must be in the format: variable1(e.g.Tissue)-ChiporControl-variable2
#(e.g.Experimentalcondition)-Furthercondition(if needed e.g. protein)
#and/orreplicate.bam
#Example: Cerebellum-Chip-minusCPT-Top1_2.bam
#Controls must have 1 as the value in the final position

#filters out reads that are unmapped, not a primary alignment or chimeric
@follows(mkdir("filtered_bams.dir"))
@transform("*.bam", regex(r"(.+).bam"),
          r"filtered_bams.dir/\1.filtered.bam")
def filterreads(infile,outfile):
    statement='''samtools view -b -o %(outfile)s -F 268 -q 30  %(infile)s'''
    job_memory="4G"
    P.run()


@follows(mkdir("deduplicated.dir"))
@transform(filterreads,
           regex(r"filtered_bams.dir/(.+).bam"),
           r"deduplicated.dir/\1.deduplicated.bam")
def removeduplicates(infile, outfile):
    temp_file=P.snip(outfile, ".deduplicated.bam") + ".temp.bam"
    metrics_file=P.snip(outfile, ".bam") + ".metrics"
    statement='''MarkDuplicates I=%(infile)s  
                                O=%(temp_file)s 
                                M=%(metrics_file)s > %(temp_file)s.log;
                                checkpoint;
                                samtools view
                                -q 30
                                -F 1024
                                -b
                                %(temp_file)s
                                > %(outfile)s;
                                checkpoint;
                                rm -r %(temp_file)s;
                                checkpoint;
                                samtools index %(outfile)s'''
    job_memory="6G"
    P.run()


#@transform(prepareBAMForPeakCalling,suffix(".prep.bam"),"deduplicated.bam")
#def removeduplicates(infile,outfile):
 #   statement='''samtools view 
  #               -F 1024
   #              -b
    #             %(infile)s
     #            > %(outfile)s'''
    #job_memory="15G"
    #P.run()

@follows("removeduplicates")
@transform(PARAMS['job_annotations'],regex(r".*.gtf.gz"),"geneset_merged.gtf")
def mergeexons(infile, outfile):
    gtfmethod=PARAMS['job_gtf2gtfmergemethod']
    statement='''zcat %(infile)s | 
                 python ~/devel/cgat/CGAT/scripts/gtf2gtf.py
                 --method=%(gtfmethod)s |
                 python ~/devel/cgat/CGAT/scripts/gtf2gtf.py
                 --method=set-transcript-to-gene >
                 %(outfile)s'''
    

    job_memory="15G"
    P.run()
                 

@follows("mergeexons")
@follows(mkdir("genecounts.dir"))
@transform(removeduplicates,regex(r"deduplicated.dir/(.+).deduplicated.bam"),add_inputs(mergeexons),r"genecounts.dir/\1.counts.txt")
def getgenecounts(infiles,outfile):
    bamfile, gtffile = infiles
    statement='''featureCounts -t exon 
                               -g gene_id
                               -a %(gtffile)s 
                               -o %(outfile)s 
                               %(bamfile)s'''

    job_memory="6G" 
    P.run()

@merge(getgenecounts, "combined_gene_counts.txt")
def mergegenecounts(infiles, outfile):
    infiles = " ".join(infiles)
    statement = '''python ~/devel/cgat/CGAT/scripts/combine_tables.py
                   --use-file-prefix -c 1,2,3,4,5,6 -k 7 --regex-filename="(.+).txt" -S %(outfile)s %(infiles)s'''
    job_memory="10G" 
    P.run()
                
@transform(PARAMS["job_annotations"],
           formatter(),
           "contigs.tsv")
def get_contigs(infile, outfile):
    '''Generate a pseudo-contigs file from the geneset, where the length of 
    each contigs is determined by the GTF entry with the highest end coordinate.
    Will not stop things going off the end on contigs, but that doesn't really
    matter for our purposes'''

    last_contig = None
    max_end = 0
    outlines = []
    for entry in GTF.iterator(IOTools.openFile(infile)):
   
        if last_contig != None and entry.contig != last_contig:
            outlines.append([last_contig, str(max_end)])
            max_end = 0
            
        max_end = max(max_end, entry.end)
        last_contig = entry.contig

    outlines.append([last_contig, str(max_end)])
    IOTools.writeLines(outfile, outlines, header=None)

#@transform(PARAMS["job_annotations"],
#           regex(".+(geneset_.+).gtf.gz"),
#           add_inputs(get_contigs),
#           r"\1.filtered.gtf.gz")

#    last_contig = None
#    max_end = 0
#    outlines = []
#    for entry in GTF.iterator(IOTools.openFile(infile)):
#
#        if last_contig and entry.contig != last_contig:
#            outlines.append([entry.contig, str(max_end)])
#            max_end = 0
#
#        max_end = max(max_end, entry.end)
#        last_contig = entry.contig
#
#    outlines.append([last_contig, str(max_end)])
#    IOTools.writeLines(outfile, outlines, header=None)

@transform(PARAMS["job_annotations"],
           formatter(),
           add_inputs(get_contigs),
           "geneset.filtered.gtf.gz")
def filter_geneset(infiles, outfile):
    geneset, genome_file = infiles
    filter_extension_up=PARAMS["job_extension_up"]
    filter_extension_down=PARAMS["job_extension_down"]


        
    statement = '''cgat gtf2gtf --method=merge-transcripts -I %(geneset)s
                   | cgat gff2bed --is-gtf -L %(outfile)s.log
                   | bedtools slop -l %(filter_extension_up)s -r %(filter_extension_down)s
                     -s -i - -g %(genome_file)s
                   | sort -k1,1 -k2,2n
                   | bedtools merge -c 4 -o count
                   | awk '$4>1'
                   | bedtools intersect -v -a %(geneset)s -b -
                   | bgzip > %(outfile)s'''
    job_memory="10G"
    P.run()

#--normalize-transcript=total-sum
#--normalize-profile=area

@follows(mkdir("profiles.dir"))
@transform(removeduplicates,regex(r"deduplicated.dir/(.+)-(.+)-(.+)-(.+).filtered.deduplicated.bam"),
           add_inputs(filter_geneset),
           r"profiles.dir/\1-\2-\3-\4.bam2geneprofile")
def geneprofiles(infiles,outfile):
    bamfile, filtered_geneset = infiles
    base=re.search(r"(profiles.dir/.+-.+-.+-.+)bam2geneprofile", outfile, flags = 0)  
    base=base.group(1)
    outputallprofiles = PARAMS["job_outputallprofiles"]
    inputpersample = PARAMS["job_inputpersample"]
    if outputallprofiles == 1:
        outputprofiles = "--output-all-profiles"
    elif outputallprofiles == 0:
        outputprofiles = ""
    statement='''python ~/devel/cgat/CGAT/scripts/bam2geneprofile.py
                 -b %(bamfile)s
                 -g %(filtered_geneset)s
                 --reporter=gene
                 -m geneprofile 
                 %(outputprofiles)s                 
                 --normalize-transcript=none
                 --normalize-profile=none
                 --merge-pairs
                 -P %(base)s%%s > 
                 %(outfile)s'''
    job_memory="6G"
    P.run()


#removed     samplenumber = re.search(r"(deduplicated.dir/.+)-ChIP-(.+)-(.+).filtered.deduplicated.bam",bamfile,flags = 0)
#    if inputpersample == 1:
#        controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
#    elif inputpersample == 0:
#        controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".filtered.deduplicated.bam"
#removed -c %(controlfile)s - find out what this does


@transform(removeduplicates,regex(r"deduplicated.dir/(.+)-(.+)-(.+)-(.+).filtered.deduplicated.bam"),
           add_inputs(filter_geneset),
           r"profiles.dir/\1-\2-\3-\4.bam2tssprofile")
def tssprofiles(infiles,outfile):
    bamfile, filtered_geneset = infiles
    base=re.search(r"(profiles.dir/.+-.+-.+-.+)bam2tssprofile", outfile, flags = 0)  
    base=base.group(1)
    outputallprofiles = PARAMS["job_outputallprofiles"]
    inputpersample = PARAMS["job_inputpersample"]
    if outputallprofiles == 1:
        outputprofiles = "--output-all-profiles"
    elif outputallprofiles == 0:
        outputprofiles = ""
    statement='''python ~/devel/cgat/CGAT/scripts/bam2geneprofile.py
                 -b %(bamfile)s
                 -g %(filtered_geneset)s
                 --reporter=gene 
                 -m tssprofile
                 %(outputprofiles)s                 
                 --merge-pairs
                 -P %(base)s%%s > 
                 %(outfile)s'''
    job_memory="6G"
    P.run()

#removed     if inputpersample == 1:
#        controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
#    elif inputpersample == 0:
#        controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".filtered.deduplicated.bam"

#removed -c %(controlfile)s - find out what this does

#    if peakcalling == 1:
#        peaks = "--broad"
#    elif peakcalling == 0:
#        peaks = "" 
#  add_inputs(r"deduplicated.dir/\1-Input-\2.filtered.deduplicated.bam"),


@follows(geneprofiles)
@merge("profiles.dir/*-*-*-*.bwa.geneprofile.matrix.tsv.gz", "combined_geneprofiles_matrix.txt")
def mergegeneprofiles(infiles, outfile):
    infiles = " ".join(infiles)
    statement = '''python ~/devel/cgat/CGAT/scripts/combine_tables.py
                   --regex-filename="profiles.dir/(.+)-(.+)-(.+).bwa.geneprofile.matrix.tsv.gz"
                   --cat pulldown,condition,replicate
                   -S %(outfile)s
                   %(infiles)s'''
    job_memory="10G"
    P.run()

@follows(tssprofiles)
@merge("profiles.dir/*-*-*-*.bwa.tssprofile.matrix.tsv.gz", "combined_tssprofiles_matrix.txt")
def mergetssprofiles(infiles, outfile):
    infiles = " ".join(infiles)
    statement = '''python ~/devel/cgat/CGAT/scripts/combine_tables.py
                   --regex-filename="profiles.dir/(.+)-(.+)-(.+).bwa.tssprofile.matrix.tsv.gz"
                   --cat pulldown,condition,replicate
                   -S %(outfile)s
                   %(infiles)s'''
    job_memory="10G"
    P.run()


@follows(mergetssprofiles)
@merge("deduplicated.dir/*.bam", "Filtered_Deduplicated_Read_Counts.tsv")
def getprocessedreadcounts(infiles, outfile):
    infiles = " ".join(infiles)
    statement = '''for i in %(infiles)s; do
        echo -e $i' \t '$(samtools view -c -F 4 $i) >> Deduplicated_Bam_Read_Numbers.tsv;
    done'''
    job_memory="20G"
    P.run()
   

@follows(mkdir("broadpeakcalling.dir"))
@transform(removeduplicates,
	   regex(r"deduplicated.dir/(.+)-ChIP-(.+)-(.+).filtered.deduplicated.bam"),
           r"broadpeakcalling.dir/\1-ChIP-\2-\3.bam.macs2")
def broadpeakcall(infile,outfile):
    bamfile = infile
    peakcalling = PARAMS["job_peakcalling"]
    peakcallingformat = PARAMS["job_peakcallingformat"]
    inputpersample = PARAMS["job_inputpersample"]
    IgG_Input = PARAMS["job_igginput"]
    IgG_input_prefix = PARAMS["job_mainsampleprefix"]
    samplenumber = re.search(r"(deduplicated.dir/.+)-ChIP-(.+)-(.+).filtered.deduplicated.bam",bamfile,flags = 0)
    if inputpersample == 1:
        if re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) != "IgG":
            controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
        elif re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) == "IgG":
            if IgG_Input == 1:
                controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
            elif IgG_Input == 0:
                controlfile = "deduplicated.dir/" + IgG_input_prefix + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"                
    elif inputpersample == 0:
        if re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) != "IgG":
            controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
        elif re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) == "IgG":
            if IgG_Input == 1:
                controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
            elif IgG_Input == 0:
                controlfile = "deduplicated.dir/" + IgG_input_prefix + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
    drctry=re.search(r"(broadpeakcalling.dir/.+-ChIP-.+-.+).bam.macs2", outfile, flags = 0)
    drc=drctry.group(1)
    statement='''macs2 callpeak -t %(bamfile)s 
                                -c %(controlfile)s
                                -g hs
                                --verbose=2
                                --broad
                                -f %(peakcallingformat)s 
                                --outdir %(drc)s
                                --tempdir %(tmpdir)s >
                                %(outfile)s'''
    job_memory="6G"
    P.run()


@follows(mkdir("narrowpeakcalling.dir"))
@transform(removeduplicates,
	   regex(r"deduplicated.dir/(.+)-ChIP-(.+)-(.+).filtered.deduplicated.bam"),
           r"narrowpeakcalling.dir/\1-ChIP-\2-\3.bam.macs2")
def narrowpeakcall(infile,outfile):
    bamfile  = infile
    peakcalling = PARAMS["job_peakcalling"]
    peakcallingformat = PARAMS["job_peakcallingformat"]
    IgG_Input = PARAMS["job_igginput"]
    IgG_input_prefix = PARAMS["job_mainsampleprefix"]
    inputpersample = PARAMS["job_inputpersample"]
    samplenumber = re.search(r"(deduplicated.dir/.+)-ChIP-(.+)-(.+).filtered.deduplicated.bam",bamfile,flags = 0)
    if inputpersample == 1:
        if re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) != "IgG":
            controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
        elif re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) == "IgG":
            if IgG_Input == 1:
                controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
            elif IgG_Input == 0:
                controlfile = "deduplicated.dir/" + IgG_input_prefix + "-Input-" + samplenumber.group(2) + "-" + samplenumber.group(3) + ".filtered.deduplicated.bam"
    elif inputpersample == 0:
        if re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) != "IgG":
            controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
        elif re.search(r"deduplicated.dir/(.+)-ChIP-.+-.+.filtered.deduplicated.bam",bamfile,flags = 0).group(1) == "IgG":
            if IgG_Input == 1:
                controlfile = samplenumber.group(1) + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
            elif IgG_Input == 0:
                controlfile = "deduplicated.dir/" + IgG_input_prefix + "-Input-" + samplenumber.group(2) + ".bwa.filtered.deduplicated.bam"
    drctry=re.search(r"(narrowpeakcalling.dir/.+-ChIP-.+-.+).bam.macs2", outfile, flags = 0)
    drc=drctry.group(1)
    statement='''macs2 callpeak -t %(bamfile)s 
                                -c %(controlfile)s
                                -g hs
                                -B --SPMR
                                --call-summits
                                --verbose=2
                                -f %(peakcallingformat)s 
                                --outdir %(drc)s
                                --tempdir %(tmpdir)s >
                                %(outfile)s'''
    job_memory="6G"
    P.run()

@transform(narrowpeakcall, regex(r"narrowpeakcalling.dir/(.+).bam.macs2"),add_inputs(r"narrowpeakcalling.dir/\1/NA_control_lambda.bdg"),r"narrowpeakcalling.dir/\1/\1.narrow_fc_signal.bw")
def foldchangebw(infiles, outfile):
    filetemplate,control = infiles
    sample=re.search(r"narrowpeakcalling.dir/(.+).bam.macs2", filetemplate, flags = 0).group(1)
    cmpfile="narrowpeakcalling.dir/" + sample + "/narrow_FE.bdg"
    sortedcmpfile="narrowpeakcalling.dir/" + sample + "/narrow_FE_sorted.bdg"
    newinfile = "narrowpeakcalling.dir/" + sample + "/NA_treat_pileup.bdg"
    logfile=outfile+".log"
    statement='''macs2 bdgcmp -t %(newinfile)s
                 -c %(control)s
                 -o %(cmpfile)s
                 -m FE ;
                 checkpoint;
                 sort -k1,1 -k2,2n %(cmpfile)s > %(sortedcmpfile)s;
                 checkpoint;
                 rm %(cmpfile)s;
                 ~/devel/bedGraphToBigWig %(sortedcmpfile)s
                 /shared/sudlab1/General/annotations/hg38_noalt_ensembl85/assembly.dir/contigs.tsv
                 %(outfile)s >> %(logfile)s;
                 checkpoint;
                 rm %(sortedcmpfile)s'''
    job_memory="8G"
    P.run()
                 
    
#@follows("geneprofiles")
#@transform("geneprofiles.dir/*geneprofile.profiles.tsv.gz", regex(r"(.+).geneprofile.profiles.tsv.gz"),r"\1.normalisedprofile.tsv.gz")
#def normaliseprofiles(infile, outfile):
#    statement = '''python ~/devel/pipeline_peaksandprofiles/pipeline_peaksandprofiles/normalise_profiles.py
#                -m %(infile)s
#                -L /dev/null
#                > %(outfile)s'''
#    job_memory="20G"
#    P.run()

# ---------------------------------------------------
# Generic pipeline tasks
@follows(broadpeakcall, getprocessedreadcounts, foldchangebw, mergegeneprofiles, mergetssprofiles, mergegenecounts)
def full():
    pass


if __name__ == "__main__":
    sys.exit(P.main(sys.argv))
