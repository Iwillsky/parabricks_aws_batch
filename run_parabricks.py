from __future__ import print_function
import os
import shutil
import uuid
import subprocess
import shlex
import boto3
from argparse import ArgumentParser

s3 = boto3.resource('s3')


def download_folder(s3_path, directory_to_download):
    """
    Downloads a folder from s3
    :param s3_path: s3 folder path
    :param directory_to_download: path to download the directory to
    :return: directory that was downloaded
    """
    cmd = 'aws s3 cp --recursive %s %s' % (s3_path, directory_to_download)

    subprocess.check_call(shlex.split(cmd))

    return directory_to_download


def download_file(s3_path, directory_to_download):
    """
    Downloads an object from s3 to a local path
    :param s3_path: s3 object path
    :param directory_to_download: directory to download to
    :return: local file path of the object
    """
    bucket = s3_path.split('/')[2]
    key = '/'.join(s3_path.split('/')[3:])

    object_name = key.split('/')[-1]

    local_file_name = os.path.join(directory_to_download, object_name)

    s3.Object(bucket, key).download_file(local_file_name)

    return local_file_name


def upload_folder(s3_path, local_folder_path, sse=True):
    """
    Uploads a local folder to S3
    :param s3_path: s3 path to upload folder to
    :param local_folder_path: local folder path
    :param sse: boolean whether to enable server-side encryption
    """
    cmd = 'aws s3 cp --recursive %s %s' % (local_folder_path, s3_path)

    if sse:
        cmd += ' --sse'

    subprocess.check_call(shlex.split(cmd))


def upload_file(s3_path, local_path):
    """
    Uploads a local file to s3 with server side encryption enabled
    :param s3_path: s3 object path
    :param local_path: local file path
    :return: response from the upload file
    """
    bucket = s3_path.split('/')[2]
    key = '/'.join(s3_path.split('/')[3:])

    response = s3.Object(bucket, key).upload_file(local_path, ExtraArgs=dict(ServerSideEncryption='AES256'))

    return response


def generate_working_dir(working_dir_base):
    """
    Creates a unique working directory to combat job multitenancy
    :param working_dir_base: base working directory
    :return: a unique subfolder in working_dir_base with a uuid
    """

    working_dir = os.path.join(working_dir_base, str(uuid.uuid4()))
    try:
        os.mkdir(working_dir)
    except Exception as e:
        print ('Could not create %s. Setting Working Directory to %s' % (working_dir, working_dir_base))
        return working_dir_base
    return working_dir


def delete_working_dir(working_dir):
    """
    Deletes working directory
    :param working_dir:  working directory
    """

    try:
        shutil.rmtree(working_dir)
    except Exception as e:
        print ('Can\'t delete %s' % working_dir)


def download_fastq_files(fastq1_s3_path, fastq2_s3_path, working_dir):
    """
    Downlodas the fastq files
    :param fastq1_s3_path: S3 path containing FASTQ with read1
    :param fastq2_s3_path: S3 path containing FASTQ with read2
    :param working_dir: working directory
    :return: local path to the folder containing the fastq
    """
    fastq_folder = os.path.join(working_dir, 'fastq')

    try:
        os.mkdir(fastq_folder)
    except Exception as e:
        pass

    local_fastq1_path = download_file(fastq1_s3_path, fastq_folder)
    local_fastq2_path = download_file(fastq2_s3_path, fastq_folder)

    return local_fastq1_path, local_fastq2_path


def upload_output(output_s3_path, local_folder_path):
    """
    Uploads results folder containing the bam file (and associated output)
    :param bam_s3_path: S3 path to upload the alignment results to
    :param local_folder_path: local path containing the alignment results
    """

    upload_folder(output_s3_path, local_folder_path)


def run_parabricks(pbrun, reference, known_sites, fastq1, fastq2, cmd_args, working_dir, num_cpus, num_gpus):
    """
    Runs Parabricks Germline
    :param pbrun: local path for pbrun
    :param reference: local path to directory containing reference
    :param known_sites: local path to directory containing known indels
    :param fastq1: FASTQ1 path
    :param fastq1: FASTQ2 path
    :param cmd_args: Command args for pbrun
    :param working_dir: working directory
    :param num_cpus: Number of vCpus for Parabricks to use
    :param num_gpus: Number of GPUs for Parabricks to use
    :return: path to results
    """

    # Maps to Parabricks's folder structure and change working directory
    os.chdir(working_dir)
    output_folder = os.path.join(working_dir, 'output')

    try:
        os.mkdir(output_folder)
    except Exception as e:
        print ('Cannot create directory at: %s' % output_folder)
        pass
    
    gvcf = '--gvcf' in [ _.strip() for _ in cmd_args.split() ]
    out_bam = os.path.join(output_folder, 'output.bam')
    out_vcf = os.path.join(output_folder, 'output.g.vcf.gz' if gvcf else 'output.vcf')
    out_recal_file = os.path.join(output_folder, 'report.txt')

    cmd = '%s germline --num-cpu-threads %s --num-gpus %s --ref %s --in-fq %s %s --knownSites %s --out-bam %s --out-variants %s --out-recal-file %s %s' % \
        (pbrun, num_cpus, num_gpus, reference, fastq1, fastq2, known_sites, out_bam, out_vcf, out_recal_file, cmd_args)
    print ("Running: %s" % cmd)
    subprocess.check_output(shlex.split(cmd), stderr=subprocess.STDOUT)

    return output_folder


def main():
    argparser = ArgumentParser()

    file_path_group = argparser.add_argument_group(title='File paths')
    file_path_group.add_argument('--fastq1_s3_path', type=str, help='FASTQ1 S3 path', required=True)
    file_path_group.add_argument('--fastq2_s3_path', type=str, help='FASTQ2 S3 path', required=True)
    file_path_group.add_argument('--reference', type=str, help='Local path to reference files.', default='/mnt/disks/local/reference/Homo_sapiens_assembly38.fasta')
    file_path_group.add_argument('--known_sites', type=str, help='Local path to knownSites vcf', default='/mnt/disks/local/reference/Homo_sapiens_assembly38.known_indels.vcf.gz')
    file_path_group.add_argument('--pbrun_path', type=str, help='Local path for pbrun', default='/opt/parabricks/pbrun')
    file_path_group.add_argument('--output_s3_folder_path', type=str, help='Output s3 path', required=True)
    
    argparser.add_argument('--num_cpu_threads', type=int, help='Number of cpu threads. Default is 16 (g4dn.12xlarge)', default=16)
    argparser.add_argument('--num_gpus', type=int, help='Number of gpus. default is 4 (g4dn.12xlarge)', default=4)
    argparser.add_argument('--working_dir', type=str, help='Base for working directory.', default='/mnt/disks/local')

    args,cmd_args = argparser.parse_known_args()

    cmd_args = ' '.join([_.strip() for _ in cmd_args])

    working_dir = generate_working_dir(args.working_dir)

    # Download fastq files and reference files
    print ('Downloading FASTQs')
    fastq1_path, fastq2_path = download_fastq_files(args.fastq1_s3_path, args.fastq2_s3_path, working_dir)
    print ('Running Parabricks Germline')
    output_folder_path = run_parabricks(args.pbrun_path, args.reference, args.known_sites, fastq1_path, fastq2_path, cmd_args, working_dir, args.num_cpu_threads, args.num_gpus)
    print ('Uploading results to %s' % args.output_s3_folder_path)
    upload_output(args.output_s3_folder_path, output_folder_path)
    print('Cleaning up working dir')
    delete_working_dir(working_dir)
    print ('Completed')

if __name__ == '__main__':
    main()
