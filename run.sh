#!/bin/bash
set -x

FASTQ1=s3://mybucket/Data/NA12878_1.fastq.gz
FASTQ2=s3://mybucket/Data/NA12878_2.fastq.gz
OUTPUT=s3://mybucket/NA12878_AWS_Batch/
STACK=parabricks-batch


JOBDEF=`aws cloudformation describe-stacks --stack-name ${STACK} --query "Stacks[0].Outputs[3].OutputValue" | awk 'BEGIN{FS="/"}{print $NF}' | sed 's/"//'`
QUEUE=`aws cloudformation describe-stacks --stack-name ${STACK} --query "Stacks[0].Outputs[4].OutputValue" | awk 'BEGIN{FS="/"}{print $NF}' | sed 's/"//'`
aws batch submit-job --job-name test-sample --job-queue ${QUEUE} --job-definition ${JOBDEF} --parameters Fastq1Path=${FASTQ1},Fastq2Path=${FASTQ2},OutputS3FolderPath=${OUTPUT},CmdArgs="--gvcf"
