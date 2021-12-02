# -*- mode:python; coding:utf-8; -*-
# author: Mariia Boldyreva <mboldyreva@cloudlinux.com>
# created: 2021-10-28

"""
Builder on AWS Instance.
"""

import os
import io
import base64
import pathlib
import logging

import boto3
import paramiko

from lib.config import settings


__all__ = ['ExecuteError', 'ParamikoWrapper', 'Builder']


class ExecuteError(Exception):
    """
    Remote command execution Exception.
    """

    pass


class ParamikoWrapper(paramiko.SSHClient):

    """
    Paramiko Wrapper for SSH Client.
    """

    def safe_execute(self, cmd, *args, **kwargs):
        """
        Executes a remote command on AWS Instance.

        Parameters
        ----------
        cmd : str
            A remote command to execute.
        """
        cmd = 'set -o pipefail; ' + cmd
        logging.info(f'Executing {cmd}')
        stdin, stdout, stderr = self.exec_command(cmd, *args, **kwargs)
        stdin.flush()
        exit_status = stdout.channel.recv_exit_status()
        if exit_status != 0:
            logging.info(f'Command output:\n{stdout.read().decode()}')
            logging.error(f'Traceback:\n{stderr.read().decode()}')
            raise ExecuteError(f'Command \'{cmd}\' execution failed.')

        return stdout, stderr


class Builder:

    """
    Builder on AWS Instance.
    """

    AWS_KEY_PATH = pathlib.Path('aws_test')

    def __init__(self):
        """
        Builder initialization.
        """
        self.ec2_client = boto3.resource(service_name='ec2',
                                         region_name='us-east-1')
        ssh_file = base64.b64decode(settings.ssh_key_file.encode()).decode()
        with open(os.open(self.AWS_KEY_PATH, os.O_CREAT | os.O_WRONLY, 0o600),
                  'w') as key_file:
            key_file.write(ssh_file)
        self.private_key = paramiko.RSAKey.from_private_key(io.StringIO(ssh_file))

    @staticmethod
    def get_ssh_client():
        """
        Gets SSH Client with paramiko.

        Returns
        -------
        builder.ParamikoWrapper
        """
        ssh_client = ParamikoWrapper()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return ssh_client

    def find_aws_instance(self, instance_ip: str):
        """
        Finds AWS Instance by it's public ip address.

        Parameters
        ----------
        instance_ip : str
            AWS Instance public ip address.

        Returns
        -------
        boto3.resources.factory.ec2.Instance
            AWS Instance data
        """
        return next(iter(self.ec2_client.instances.filter(
            Filters=[{'Name': 'ip-address', 'Values': [instance_ip]}]
        )))

    def ssh_aws_connect(self, instance_ip: str, hypervisor: str):
        """

        Parameters
        ----------
        instance_ip : str
            AWS Instance public ip address.
        hypervisor : str
            Hypervisor name.

        Returns
        -------
        builder.ParamikoWrapper
        """
        logging.info(f'Connecting to instance {instance_ip}')
        instance = self.find_aws_instance(instance_ip)
        ssh_client = self.get_ssh_client()
        if hypervisor.lower() != 'hyperv':
            ssh_client.connect(
                instance.public_dns_name,
                username='ec2-user',
                pkey=self.private_key
            )
        else:
            ssh_client.connect(
                instance.public_dns_name,
                username='Administrator',
                pkey=self.private_key
            )
        return ssh_client