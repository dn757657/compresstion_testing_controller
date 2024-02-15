import logging
import threading
import time
import os
import glob
import uuid
import paramiko

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from sqlalchemy import select
import numpy as np
from dotenv import load_dotenv
from os.path import join, dirname

from compression_testing_data.main import parse_gphoto_config_for_sql, parse_cam_config_dict_for_gphoto, parse_sql_gphoto_config_for_gphoto
from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.acquisition_settings import CameraSetting
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, Frame

from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings, eosr50_continuous_capture_and_save    
from compression_tester_controls.sys_protocols import platon_setup, init_cameras, sys_init, home_camera_system, capture_step_frames, camera_system_setup
from compression_tester_controls.sys_functions import sample_force_sensor, get_a201_Rf, move_big_stepper_to_setpoint

from file_management import transfer_files

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)
CONN_STR = 'postgresql://domanlab:dn757657@192.168.1.2:5432/compression_testing'


def store_camera_settings(port = None):
    if not port:
        ports = gphoto2_get_active_ports()
        port = ports[0]

    # get camera settings table columns
    cam_settings_sql = [column.key for column in CameraSetting.__table__.columns]
    sql_settings_exclude = ['id', 'created_at']  # filter out non camera settings
    cam_settings_sql = [x for x in cam_settings_sql if x not in sql_settings_exclude]

    config = gpohoto2_get_camera_settings(port=port, config_options=cam_settings_sql)
    logging.info(f"Retrieving Settings: {cam_settings_sql} from Camera @ {port}")

    dict_config = parse_gphoto_config_for_sql(config_output=config)
    logging.info(f"Storing: {dict_config}")

    session = Session()
    session.add(CameraSetting(**dict_config))
    session.commit()
    session.close()
    logging.info(f"Stored Current Camera Settings.")

    pass


def get_cam_settings(id: int = 1):
    Session = get_session(conn_str='postgresql://domanlab:dn757657@192.168.1.2:5432/compression_testing')
    session = Session()

    stmt = select(CameraSetting).where(CameraSetting.id == id)
    slct = session.execute(stmt)

    settings = slct.scalars().all()
    if len(settings) > 1:
        logging.info("found too many camera settings?")
        return
    else:
        setting = settings[0]

    setting = parse_sql_gphoto_config_for_gphoto(camera_setting=setting)

    print(f"gphoto settings: {setting}")

    return setting


def counts_to_mm(encoder_steps):
    mm = encoder_steps * (6/1000)
    return mm


def mm_to_counts(mm):
    encoder_steps = mm / (6/1000)
    return int(round(encoder_steps))


def find_force_sensor_Rf():
    components = sys_init()
    sample_force_sensor(n_samples=100, components=components)
    # get_a201_Rf(n_samples=100, components=components, rs=987)

    return

def run_trial(
        trial_id: int = 1,
        cam_settings_id = 1,
        ):
    Session = get_session(conn_str=CONN_STR)
    session = Session()

    trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
    sample = session.query(Sample).filter(Sample.id == trial.sample.id).first()
    if trial and sample:
        components = sys_init()

        # for testing
        encoder_zero_count = 7776
        encoder_sample_height_count = 4797

        sample_height_counts = abs(encoder_zero_count - encoder_sample_height_count)
        sample_height_mm = counts_to_mm(sample_height_counts)
        sample.height_enc = sample_height_mm
        session.commit()
        logging.info(f"Sample Height: {sample_height_mm}")

        force_zero = np.mean(sample_force_sensor(n_samples=100, components=components))
        trial.force_zero = force_zero
        session.commit()
        logging.info(f"Force Zero: {force_zero}")

        camera_system_setup(components=components)

        strain_min = 0
        desired_strain_limit = trial.strain_limit
        desired_strain_delta = trial.strain_delta_target 
        force_limit = trial.force_limit

        step_strain_target = strain_min
        while True:
            # compression_dist_mm = sample_height_mm * step_strain_target
            # compression_dist_encoder_counts = mm_to_counts(compression_dist_mm)
            # stepper_setpoint = encoder_sample_height_count - compression_dist_encoder_counts
            
            logging.info(f"Running Trial Step")

            run_trial_step(
                components=components,
                session=session,
                step_strain_target=step_strain_target,
                sample_height_mm=sample_height_mm,
                encoder_sample_height_count=encoder_sample_height_count,
                trial_id=trial_id,
                cam_settings_id=cam_settings_id,
                postgres_db_dir='/share/CACHEDEV1_DATA/Public/postgres_data',
                dest_machine_addr='192.168.1.2',
                dest_machine_user='domanlab'
            )

            step_strain_target += desired_strain_delta

            if step_strain_target > desired_strain_limit:
                logging.info("Strain limit reached! Trial Complete")
                break

            # create steps - ensure first step is zero - limit to 2mm max compression
            # run steps one by one
            # move platon
            # check for force overload
            # get photos

            # run_trial_step(components=components)
        # move platon back to zero70007
    
    else:
        logging.info(f"Trial with ID: {trial_id} not found!")
    return

def run_trial_step(
        components,
        session,
        step_strain_target: float,
        sample_height_mm: float,
        encoder_sample_height_count: int,
        trial_id: int,
        cam_settings_id: int = 1,
        postgres_db_dir: str = '/share/CACHEDEV1_DATA/Public/postgres_data',
        dest_machine_addr: str = '192.168.1.2',
        dest_machine_user: str = 'domanlab'
        ):

    new_step = CompressionStep(
        name=uuid.uuid4(),
        strain_target=step_strain_target,
        compression_trial_id=trial_id
    )
    session.add(new_step)
    session.commit()
    new_step_id = new_step.id

    enc = components.get('e5')

    compression_dist_mm = sample_height_mm * step_strain_target
    compression_dist_encoder_counts = mm_to_counts(compression_dist_mm)
    stepper_setpoint = encoder_sample_height_count - compression_dist_encoder_counts

    # move platon - stop at max force - modify func to stop at max force
            # need to use threading to run force sensor and stepper move
            # move_big_stepper_to_setpoint(
                # components=components, 
                # setpoint=stepper_setpoint, 
                # error=5
                # )
    
    new_sample_height_counts = abs(enc.read() - encoder_sample_height_count)
    new_sample_height_mm = counts_to_mm(new_sample_height_counts)
    actual_strain = 1 - (new_sample_height_mm / sample_height_mm)
    new_step.strain_encoder = actual_strain


    force = np.mean(sample_force_sensor(n_samples=100, components=components))
    new_step.force = force
    session.commit()
    print(f"Force @ Strain {actual_strain}: {force}")

    cam_settings = get_cam_settings(id=cam_settings_id)  # get cam settings from steps object!
    cam_ports = init_cameras(cam_settings=cam_settings)
    
    # photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=500)

    cam_threads = []
    photos = [list() for x in cam_ports]
    stop_event = threading.Event()

    for i, port in enumerate(cam_ports, start=0):
        cam = threading.Thread(
                target=eosr50_continuous_capture_and_save,
                args=(port, stop_event, photos[i])
            )
        cam_threads.append(cam)

    for thread in cam_threads:
        thread.start()
    start = time.time()
    while True:
        if time.time() - start > 10:
            stop_event.set()
            for thread in cam_threads:
                thread.join()
            break
    photo_list = [item for sublist in photos for item in sublist]

    # move files to db store
    current_directory = os.getcwd()
    absolute_filepaths_rpi = [filepath for name in photo_list for filepath in glob.glob(os.path.join(current_directory, f"{name}.*"))]
    trial_frames_dir = f'{postgres_db_dir}/trial_id_{str(trial_id)}'
    move_frames_scp(
        absolute_filepaths=absolute_filepaths_rpi,
        frames_dir=trial_frames_dir,
        dest_machine_user=dest_machine_user,
        dest_machine_addr=dest_machine_addr
    )

    filenames = [os.path.basename(filepath) for filepath in absolute_filepaths_rpi]
    for filename in filenames:
        name = os.path.splitext(filename)[0]
        file_ext = os.path.splitext(filename)[1].strip(".")
        new_frame = Frame(
            name=name,
            file_extension=file_ext,
            file_name=filename,
            filepath=f'{trial_frames_dir}/{filename}',
            camera_setting_id=cam_settings_id,
            compression_step_id=new_step_id
        )
        session.add(new_frame)
    session.commit()

    # photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=500)
    # print(f"step Photos: {photo_list}")
    # move photos to server
    # enter photos in server db

    return

def move_frames_scp(
        absolute_filepaths,
        frames_dir: str,
        dest_machine_user: str = 'domanlab',
        dest_machine_addr: str = '192.168.1.2'):

    dest_pass = os.environ.get('DOMANLAB_PASS')

    check_and_create_directory(
        host_name=dest_machine_addr,
        port=22,
        username=dest_machine_user,
        directory=frames_dir
    )

    transfer_files(
        file_list=absolute_filepaths,
        dest_machine_dir=frames_dir,
        dest_machine_user=dest_machine_user,
        dest_machine_addr=dest_machine_addr,
        interfaces=['eth0'],
        dest_pass=dest_pass
    )

    pass


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


if __name__ == '__main__':
    run_trial()