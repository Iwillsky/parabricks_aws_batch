# Getting Started with Parabricks on AWS

Welcome! This guide details how to get started using Parabricks on AWS. There are several key topics for getting started. We recommend you familiarize yourself with the following topics prior to starting:
* [Parabricks Documentation](https://www.nvidia.com/en-us/docs/parabricks/)
* [AWS Batch](https://aws.amazon.com/batch/)
* [Docker](https://docs.docker.com/)
* [Amazon Elastic Compute Cloud (EC2)](https://aws.amazon.com/ec2/)
* [Amazon Elastic Container Registry](https://aws.amazon.com/ecr/)
* [AWS Identity and Access Management](https://aws.amazon.com/iam/)
* [Amazon VPC](https://aws.amazon.com/vpc/)

## How the software is packaged and deployed

NVIDIA is offering Parabricks through an Amazon Machine Image (AMI). Please follow the instructions from NVIDIA to obtain the AMI. **You will need an AWS account**

In order to elastically scale to your compute requirements, this architecture uses AWS Batch to submit secondary analysis jobs to Parabricks on g4dn.12xlarge EC2 instances. By default, the wrapper script contains capabilities to run germline analyses using GPU-accelerated BWA-MEM+GATK. If you wish to run a separate analysis, you will need to modify the command in `run_parabricks.py`

## Getting Started

### Step 1. Determine the Amazon VPC and Subnets to run Parabricks.

You may either (1) use an existing Amazon VPC or (2) create a new Amazon VPC.

1. *Existing VPC*: We recommend any existing VPC that you use has at least two private subnets spread across at least two AWS Availability Zones. Additionally, please be sure to have [S3 VPC endpoints](https://docs.aws.amazon.com/vpc/latest/userguide/vpce-gateway.html) set up for your VPC. 

2. *New VPC*: We recommend using the [AWS Quick Start](https://aws.amazon.com/quickstart/architecture/vpc/) to deploy a new Amazon VPC [

For either, please note the subnet-ids and vpc-id, as you will need them shortly.

### Step 2. Create your Docker Container

AWS Batch uses Docker to run compute jobs. However, because Parabricks is provided as an AMI, we shall create a lightweight Docker container that allows AWS Batch to talk to the EC2 Instance with the Parabricks AMI. We will store this Docker Image in Amazon ECR (see https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html)

In the below code, replace `ACCOUNT_ID` with your 12-digit AWS account ID, and the region (us-east-1) with whichever region you run in.

```
# Create an Amazon ECR registry
aws ecr create-repository --repository-name parabricks-aws

# Authenticate
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com

# Build, tag, and push container
make REGISTRY=ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com
```

### Step 3. Deploy your AWS Batch Compute Environments, Job Queues, and Job Definition
The BoM comes with `deploy_parabricks.template.yaml`. This CloudFormation script sets up your AWS Batch environment. Replace your `VpcId` and `SubnetIds` with the ones you noted earlier. Also, you will need an S3 bucket which has your genomics data (eg FASTQ). If you do not have a bucket, `S3BucketName` should be set to your desired bucket name, which also contains the reference data used by Parabricks (see `ReferenceS3URI` below). Modify the rest below.

```
STACK=parabricks-batch
aws cloudformation create-stack --stack-name $STACK --template-body file://deploy_parabricks.template.yaml --capabilities CAPABILITY_IAM --parameters \
ParameterKey=VpcId,ParameterValue=vpc-37291250 \
ParameterKey=SubnetIds,ParameterValue=subnet-ff8638b6\\,subnet-9c36f4c7 \
ParameterKey=S3BucketName,ParameterValue=mybucket \
ParameterKey=ContainerURI,ParameterValue=123456789012.dkr.ecr.us-east-1.amazonaws.com/parabricks-aws:2.5 \
ParameterKey=ImageId,ParameterValue=ami-08ff18ff8e98d47df \
ParameterKey=Ec2KeyPair,ParameterValue=mykey\
ParameterKey=MaxvCpus,ParameterValue=240 \
ParameterKey=ReferenceS3URI,ParameterValue="s3://mybucket/nvidia_parabricks/Ref/"
```

Deployment of the environment should take several minutes. Here is what you create:

* An AWS Batch Compute Environment to optimize for AWS Spot pricing for g4dn.12xlarge.
* An AWS Batch Compute Environment for on-demand pricing for g4dn.12xlarge.
* An AWS Batch Job Queue that prioritizes spot pricing and then uses on-demand if the spot price is too high **or** capacity for the spot compute environment is full (specified by `MaxvCpus` above).
* An AWS Batch Job Definition that specifies how to run Parabricks. This job definition, and the underlying container, are currently configured to run germline variant calling (`pbrun germline`) with default parameters.
* Several other resources supporting the above (IAM, EC2 Launch Template, etc.)

You can get the output of your deployment using `aws cloudformation describe-stacks --stack-name parabricks-batch`. 

### Step 4. Test the deployment
To deploy with AWS Batch you need to know:
1. The Job Definition for your job
2. The AWS Batch Job Queue to use
3. Any parameters to add in. In general, these may be FASTQ paths and where to submit the output to.

NVIDIA provies a sample set of FASTQs to test your deployment. Analysis of this sample should take ~10-15 min.

```
JOBDEF=`aws cloudformation describe-stacks --stack-name parabricks-batch --query "Stacks[0].Outputs[3].OutputValue" | awk 'BEGIN{FS="/"}{print $NF}' | sed 's/"//'`
QUEUE=`aws cloudformation describe-stacks --stack-name parabricks-batch --query "Stacks[0].Outputs[4].OutputValue" | awk 'BEGIN{FS="/"}{print $NF}' | sed 's/"//'`
FASTQ1=s3://mybucket/Data/sample_1.fq.gz
FASTQ2=s3://mybucket/Data/sample_2.fq.gz
OUTPUT=s3://mybucket/test_batch_sample/
aws batch submit-job --job-name test-sample --job-queue $QUEUE --job-definition $JOBDEF --parameters Fastq1Path=$FASTQ1,Fastq2Path=$FASTQ2,OutputS3FolderPath=$OUTPUT,CmdArgs="--gvcf"
```

The job will spin up in the AWS Batch dashboard and will be in a `RUNNABLE` state until AWS Batch spins up a new instance. Once the instance is ready, you will see the job move from a `RUNNABLE` state to `STARTING` to `RUNNING`. During the instance boot, the NVME SSD drive is mounted to `/mnt/disks/local` and the reference data is downloaded from S3 to that drive.

Once the job finishes, you can find the output in the `OUTPUT` path you specified previously.

`aws s3 ls ${OUTPUT}`

### Step 5. Sequence and analyze to your heart's content!

### Pre-configured scripts
All the steps above have been put into two scripts:
1. setup.sh - It creates the AWS Batch environment
2. run.sh - Running the analysis 
You will have to setup the variables in the two scripts appropriately.
setup.sh and run.sh have STACK variable in common and you must create the stack mentioned in STACK variable in run.sh by running the setup.sh with the same STACK variable

