FROM nvidia/cuda:10.2-devel-ubuntu16.04
#FROM ubuntu:16.04

# Install any packages required for parabricks
#RUN yum update -y && yum install -y epel-release && yum clean all
RUN apt-get update \ 
  && apt-get install -y apt-transport-https \
  ca-certificates \
  curl \
  gnupg-agent \
  software-properties-common \
  python-pip && apt-get clean

RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add - \
  && add-apt-repository \
  "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

RUN apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io && apt-get clean

RUN pip install --upgrade pip && pip install boto3 awscli --upgrade

RUN distribution=$(. /etc/os-release;echo $ID$VERSION_ID) \
  && curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | apt-key add - \
  && curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | tee /etc/apt/sources.list.d/nvidia-docker.list \
  && apt-get update && apt-get install -y nvidia-container-toolkit \
  && apt-get clean

# Landing directory should be where the run script is located
WORKDIR "/"

# Copy wrapper in
COPY run_parabricks.py /
COPY nvidia-docker /usr/bin/ 
RUN chmod +x /usr/bin/nvidia-docker

# Default behaviour. Over-ride with --entrypoint on docker run cmd line
ENTRYPOINT ["python", "/run_parabricks.py"]