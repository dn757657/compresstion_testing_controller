import logging
import os
import subprocess
import paramiko
import shutil
import os

from typing import List

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


def transfer_files(
        file_list: List[str],
        dest_machine_user: str,
        dest_machine_addr: str,
        dest_machine_dir: str,
        dest_pass: str,
        interfaces: List[str],
        remove_after=False
):
    """

    :param file_list:
    :param dest_machine_addr:
    :param dest_machine_dir:
    :param dest_machine_user:
    :param interfaces: order by priority
    :param remove_after:
    :return:
    """

    use_interface = None
    for interface in interfaces:
        if os.system(f"ip link show {interface}") == 0:
            use_interface = interface

    if not use_interface:
        logging.info("No connection found in interfaces")

    # Replace these with actual destination machine details
    dest_machine = f"{dest_machine_user}@{dest_machine_addr}"
    for file in file_list:
        # Constructing the SCP command
        scp_command = f"sshpass -p {dest_pass} " \
                      f"scp -o BindInterface={use_interface} {file} " \
                      f"{dest_machine}:{dest_machine_dir}"
        try:
            subprocess.run(scp_command, check=True, shell=True)
            print(f"Transferred {file}:{dest_machine_dir} successfully.")

            # Optionally remove the file after transfer
            if remove_after:
                os.remove(file)
                print(f"Removed {file} after transfer.")
        except subprocess.CalledProcessError as e:
            print(f"Error in transferring {file}: {e}")

    pass


def bash_to_windows_paths(bash_paths, bash_machine_ip):
    windows_paths = list()
    for path in bash_paths:
        s = path.split("/")
        end = s[3:]
        end = "\\".join(end)
        win_fp = f"\\\{bash_machine_ip}\\{end}"
        windows_paths.append(win_fp)
    
    return windows_paths


def move_trial_assets(
        absolute_asset_filepaths,
        interfaces,
        dest_asset_dir: str,
        dest_machine_user: str = 'domanlab',
        dest_machine_addr: str = '192.168.1.3'):

    dest_pass = os.environ.get('DOMANLAB_PASS')

    check_and_create_directory(
        hostname=dest_machine_addr,
        port=22,
        username=dest_machine_user,
        password=dest_pass,
        directory=dest_asset_dir
    )

    transfer_files(
        file_list=absolute_asset_filepaths,
        dest_machine_dir=dest_asset_dir,
        dest_machine_user=dest_machine_user,
        dest_machine_addr=dest_machine_addr,
        interfaces=interfaces,
        dest_pass=dest_pass,
        remove_after=True
    )

    pass


def move_file(source, destination):
    """
    Moves a file from the source path to the destination path with checks for existence.

    Parameters:
    - source (str): The path of the file to be moved.
    - destination (str): The path where the file should be moved to.

    Returns:
    - str: Description of the outcome.
    """
    # Check if the source file exists
    if not os.path.exists(source):
        return "Error: Source file does not exist."

    # Check if the destination is a directory that does not exist and create it if necessary
    destination_dir = os.path.dirname(destination)
    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir, exist_ok=True)
        except Exception as e:
            return f"Error creating destination directory: {e}"

    # Attempt to move the file
    try:
        shutil.move(source, destination)
        return f"File moved successfully to {destination}"
    except Exception as e:
        return f"Error moving file: {e}"


def check_and_create_directory(hostname, port, username, password, directory):
    """
    Check if a directory exists on a remote device via SSH and create it if it does not exist.

    :param hostname: The hostname or IP address of the remote device.
    :param port: The port number to use for SSH.
    :param username: The username for SSH authentication.
    :param password: The password for SSH authentication.
    :param directory: The directory to check and potentially create.
    """
    # Initialize SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        # Connect to the remote device
        client.connect(hostname, port, username, password)
        
        # Check if the directory exists
        stdin, stdout, stderr = client.exec_command(f'test -d {directory} || mkdir -p {directory}')
        stderr_output = stderr.read().decode().strip()
        
        if stderr_output:
            print(f"Error checking/creating directory: {stderr_output}")
        else:
            print(f"Directory checked/created successfully: {directory}")
    except Exception as e:
        print(f"SSH connection or command execution failed: {e}")
    finally:
        client.close()


# Example usage
# files_to_transfer = []
# root_dir = "/home/daniel/repos/photo_test/"
# for i in range(0, 100):
#     filename = f"test_capture_{i}.jpg"
#     files_to_transfer.append(f"{root_dir}{filename}")  # need to resolve file locations (repos in different files)

# dest_pass = input("enter ssh destination machine password")

# dest_dir = '/share/CACHEDEV1_DATA/Public/postgres_data/frames_temp/'

# destination_directory = "C:/Users/Daniel/home/data/compression_tester_trials/transfer_testing"
# transfer_files(
#     file_list=files_to_transfer,
#     dest_machine_dir=destination_directory,
#     dest_machine_user='daniel',
#     dest_machine_addr='134.190.197.31',
#     interfaces=['eth0', 'wlan0'],
#     dest_pass=dest_pass
# )
