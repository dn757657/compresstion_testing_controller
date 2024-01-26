import logging
import os
import subprocess

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

    # TODO ammend command to
    #  sshpass -p 7576576056 scp -o BindInterface=wlan0 /home/daniel/repos/photo_test/test_capture_0.jpg daniel@134.190.197.31:C:/Users/Daniel/home/data/compression_tester_trials/transfer_testing
    #  maybe store password on machine?

    for file in file_list:
        # Constructing the SCP command
        scp_command = f"sshpass -p {dest_pass} " \
                      f"scp -o BindInterface={use_interface} {file} " \
                      f"{dest_machine}:{dest_machine_dir}"
        try:
            subprocess.run(scp_command, check=True, shell=True)
            print(f"Transferred {file} successfully.")

            # Optionally remove the file after transfer
            if remove_after:
                os.remove(file)
                print(f"Removed {file} after transfer.")
        except subprocess.CalledProcessError as e:
            print(f"Error in transferring {file}: {e}")


# Example usage
files_to_transfer = []
root_dir = "/home/daniel/repos/photo_test/"
for i in range(0, 100):
    filename = f"test_capture_{i}.jpg"
    files_to_transfer.append(f"{root_dir}{filename}")  # need to resolve file locations (repos in different files)

dest_pass = input("enter ssh destination machine password")

destination_directory = "C:/Users/Daniel/home/data/compression_tester_trials/transfer_testing"
transfer_files(
    file_list=files_to_transfer,
    dest_machine_dir=destination_directory,
    dest_machine_user='daniel',
    dest_machine_addr='134.190.197.31',
    interfaces=['eth0', 'wlan0'],
    dest_pass=dest_pass
)
