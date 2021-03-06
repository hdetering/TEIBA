#!/usr/bin/env python
#coding: utf-8


#### FUNCTIONS ####
def header(string):
    """
        Display  header
    """
    timeInfo = time.strftime("%Y-%m-%d %H:%M")
    print '\n', timeInfo, "****", string, "****"


def subHeader(string):
    """
        Display  subheader
    """
    timeInfo = time.strftime("%Y-%m-%d %H:%M")
    print timeInfo, "**", string, "**"


def info(string):
    """
        Display basic information
    """
    timeInfo = time.strftime("%Y-%m-%d %H:%M")
    print timeInfo, string


def gt2binary(genotype):
    """
    Convert the genotype of a germline variant absent in the reference genome into binary: 1 (carrier) and 0 (not carrier). 
    """
   
    # A) Homozygous alternative, heterozygous or haploid carrier
    if (genotype == '1/1') or (genotype == '0/1') or (genotype == '1'):
        boolean = 1

    # B) Homozygous reference, haploid not carrier or unknown genotype
    else:
        boolean = 0

    return boolean

def gt2binary_ref(genotype):
    """
    Convert the genotype of a germline variant in the reference genome into binary: 1 (carrier) and 0 (not carrier). 
    """
   
    # A) Homozygous reference, heterozygous or haploid carrier
    if (genotype == '0/0') or (genotype == '0/1') or (genotype == '0'):
        boolean = 1

    # B) Homozygous alternative, haploid not carrier or unknown genotype
    else:
        boolean = 0

    return boolean

#### MAIN ####

## Import modules ##
import argparse
import sys
import os.path
import time
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from scipy import stats
import seaborn as sns
import scipy
import formats

## Get user's input ##
parser = argparse.ArgumentParser(description= """""")
parser.add_argument('vcf', help='Multisample VCF containing genotyped MEI')
parser.add_argument('metadata', help='PCAWG donor metadata')
parser.add_argument('fileName', help='Output file name')
parser.add_argument('-o', '--outDir', default=os.getcwd(), dest='outDir', help='output directory. Default: current working directory.' )

args = parser.parse_args()
inputVCF = args.vcf
metadata = args.metadata
fileName = args.fileName
outDir = args.outDir

scriptName = os.path.basename(sys.argv[0])

## Display configuration to standard output ##
print
print "***** ", scriptName, " configuration *****"
print "vcf: ", inputVCF
print "metadata: ", metadata
print "fileName: ", fileName
print "outDir: ", outDir
print
print "***** Executing ", scriptName, ".... *****"
print

## Start ## 

#### 0. Make metadata dataframe
###############################
header("0. Make metadata dataframe")

metadataFile = open(metadata, 'r')

metadataDict = {}

for line in metadataFile:

     # Skip header
    if not line.startswith("#"):

        line = line.rstrip('\n')
        line = line.split('\t')

        donorId = line[0]
        exclusion = line[2]

        # Only select those donors that passes all the filters
        if (exclusion == 'Whitelist'):
            ancestry = line[4]
            projectCode = line[5]
            tumorType = line[6]


            metadataDict[donorId] = {}
            metadataDict[donorId]['ancestry'] = ancestry
            metadataDict[donorId]['projectCode'] = projectCode
            metadataDict[donorId]['tumorType'] = tumorType       

metadataDf = pd.DataFrame(metadataDict) 
metadataDf = metadataDf.T

#### 1. Read input multi-sample VCF and generate a VCF object
###############################################################
header("1. Process multi-sample VCF as input")

VCFObj = formats.VCF()
donorIdList = VCFObj.read_VCF_multiSample(inputVCF)


#### 2. Build dictionaries with donor genotypes
########################################################################
# Split variants into two different dictionaries depending on if they are absent or not in the reference genome. 
# Nested dictionary format:
# key1 (MEIid) -> value (dict2)
#                   key2 (donorId)     ->   value (genotype)      

header("2. Build dictionaries with donor genotypes")

genotypesDict = {} # genotypes for variants absent the reference genome
genotypesRefDict = {} # genotypes for variants in the reference genome

## For each MEI
for MEIObj in VCFObj.lineList:

    ## MEI identifier
    # A) MEI corresponds to a germline source element -> use source element identifier
    if ('SRCID' in MEIObj.infoDict):

        MEIid = MEIObj.infoDict['SRCID']

    # B) MEI does not correspond a source element -> create coordinates based identifier
    else:

        MEIid = MEIObj.infoDict["CLASS"] + '_' + MEIObj.chrom + '_' + str(MEIObj.pos)

    ## Split variants in two different dictionaries:
    # A) MEI absent in reference genome
    if (MEIObj.alt == "<MEI>"):

        genotypesDict[MEIid] = {}
     
        # For each donor and genotype
        for donorId, genotypeField in MEIObj.genotypesDict.iteritems():

            genotypeFieldList = genotypeField.split(":")
            genotype = genotypeFieldList[0]
    
            genotypesDict[MEIid][donorId] = genotype

    ## B) MEI in the reference genome 
    elif (MEIObj.ref == "<MEI>"):

        genotypesRefDict[MEIid] = {}
     
        # For each donor and genotype
        for donorId, genotypeField in MEIObj.genotypesDict.iteritems():

            genotypeFieldList = genotypeField.split(":")
            genotype = genotypeFieldList[0]
    
            genotypesRefDict[MEIid][donorId] = genotype

    ## C) Raise error...  
    else:
        msg="Incorrectly formated VCF line"
        info(msg)
 

#### 3. Convert dictionaries into dataframes specifying 
########################################################
# donor status (1:carrier, 0:not_carrier)
###########################################

header("3. Convert dictionaries into dataframes specifying donor status")

### A) Variant absent in reference genome

genotypesDf = pd.DataFrame(genotypesDict) 
genotypesDf = genotypesDf.T
genotypesBinaryDf = genotypesDf.applymap(gt2binary)

### B) Variant in the reference genome 
genotypesRefDf = pd.DataFrame(genotypesRefDict) 
genotypesRefDf = genotypesRefDf.T
genotypesRefBinaryDf = genotypesRefDf.applymap(gt2binary_ref)

#### 4. Compute the number of different variants each donor carries
#####################################################################

header("4. Compute the number of different variants each donor carries")

## Concatenate dataframes
dataframeList = [genotypesBinaryDf, genotypesRefBinaryDf]
genotypesAllBinaryDf = pd.concat(dataframeList)

## Compute the total number of MEI per donor 
nbMEIperDonorSeries = genotypesAllBinaryDf.sum(axis=0)
outputDf = metadataDf.assign(nbMEI=nbMEIperDonorSeries.values)


#### 5. Save into output file
##############################

header("5. Save into output file")

outFilePath = outDir + '/' + fileName + '.tsv'
outputDf.to_csv(outFilePath, sep='\t') 

#### End
header("FINISH!!")


