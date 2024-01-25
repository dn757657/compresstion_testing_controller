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
        scp_command = f"scp -o BindAddress={use_interface} {file} {dest_machine}:{dest_machine_dir}"
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
files_to_transfer = ["/path/to/file1", "/path/to/file2"]
destination_directory = "/remote/path"
transfer_files(files_to_transfer, destination_directory, remove_after=True)
