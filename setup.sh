#!/bin/bash
set -x

ACCOUNT_ID=111111111111    # Your AWS account ID
VPC_ID=vpc-11111111        # The VPC in which you want to run Parabricks
SUBNET_ID=subnet-11111111  # subnet-id where to run an instance within a zone
AWS_KEY=myaws-key          # The key with which you launch an instance
ReferenceURI="s3://mybucket/Ref/" # The s3 bucket location where you have the Reference for the analysis. Should be the folder that contains the bwa-index for the reference as well.
S3BucketName=mybucket
STACK=parabricks-batch
ECS_REGISTRY=parabricks-aws

aws ecr create-repository --repository-name ${ECS_REGISTRY}
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
make REGISTRY=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

aws cloudformation create-stack --stack-name ${STACK} --template-body file://deploy_parabricks.template.yaml --capabilities CAPABILITY_IAM --parameters \
 ParameterKey=VpcId,ParameterValue=${VPC_ID} \
 ParameterKey=SubnetIds,ParameterValue=${SUBNET_ID} \
 ParameterKey=S3BucketName,ParameterValue=${S3BucketName} \
 ParameterKey=ContainerURI,ParameterValue=${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/parabricks-aws:2.5 \
 ParameterKey=ImageId,ParameterValue=ami-0a65cbdbfbf7e3afe \
 ParameterKey=Ec2KeyPair,ParameterValue=${AWS_KEY}\
 ParameterKey=MaxvCpus,ParameterValue=240 \
 ParameterKey=ReferenceS3URI,ParameterValue=${ReferenceURI}

