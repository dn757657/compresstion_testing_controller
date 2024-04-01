import logging
import threading
import time
import os
import glob
import uuid
import paramiko
import random

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from sqlalchemy import select
import numpy as np
from dotenv import load_dotenv
from os.path import join, dirname

from compression_testing_data.main import parse_gphoto_config_for_sql, parse_cam_config_dict_for_gphoto, parse_sql_gphoto_config_for_gphoto
from compression_testing_data.meta import get_session
from compression_testing_data.models.samples import Print, Sample, Phantom
from compression_testing_data.models.acquisition_settings import CameraSetting
from compression_testing_data.models.reconstruction_settings import MetashapePlyExportSetting, MetashapePlyGenerationSetting, Open3DDBSCANClusteringSetting, Open3DSegmentationSetting
from compression_testing_data.models.testing import CompressionTrial, CompressionStep, Frame

from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings, eosr50_continuous_capture_and_save    
from compression_tester_controls.sys_protocols import platon_setup, init_cameras, sys_init, home_camera_system, capture_step_frames, camera_system_setup
from compression_tester_controls.sys_functions import sample_force_sensor, get_a201_Rf, move_stepper_PID_target

from file_management import move_trial_assets

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)



def add_default_camera_params(session):

    default_settings = CameraSetting(
        autopoweroff=0,
        capture=0, 
        imageformat=0, 
        iso=10,
        focusmode=0,
        aspectratio=0,
        aperture=4,
        shutterspeed=37
    )

    session.add(default_settings)
    session.commit()
    
    pass


def store_camera_settings(session, port = None):
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

    session.add(CameraSetting(**dict_config))
    session.commit()
    session.close()
    logging.info(f"Stored Current Camera Settings.")

    pass


def get_cam_settings(session, id: int = 1):

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

    return


def run_trial(
        db_conn: str,
        trial_id: int = 1,
        cam_settings_id = 1,
        server_ip = '192.168.137.199',
        is_calibration: bool = False
        ):
    Session = get_session(conn_str=db_conn)
    session = Session()

    trial = session.query(CompressionTrial).filter(CompressionTrial.id == trial_id).first()
    if trial:
        components = sys_init()
        if trial.sample:
            sample = session.query(Sample).filter(Sample.id == trial.sample.id).first()
        else:
            sample = None

        if trial.phantom:
            phantom = session.query(Phantom).filter(Phantom.id == trial.phantom.id).first()
        else:
            phantom = None

        if sample and not phantom:
            # components = sys_init()

            force_zero = np.mean(sample_force_sensor(n_samples=100, components=components))
            trial.force_zero = force_zero
            session.commit()
            logging.info(f"Force Zero: {force_zero}")

            encoder_zero_count, encoder_sample_height_count = platon_setup(components=components) 
            sample_height_counts = abs(encoder_zero_count - encoder_sample_height_count)
            sample_height_mm = counts_to_mm(sample_height_counts)
            sample.height_enc = sample_height_mm
            session.commit()
            logging.info(f"Sample Height: {sample_height_mm}")

            # force_zero = np.mean(sample_force_sensor(n_samples=100, components=components))
            # trial.force_zero = force_zero
            # session.commit()
            # logging.info(f"Force Zero: {force_zero}")

            camera_system_setup(components=components)

            strain_min = 0
            desired_strain_limit = trial.strain_limit
            desired_strain_delta = trial.strain_delta_target 
            force_limit = trial.force_limit

            step_strain_target = strain_min
            while True:
                logging.info(f"Running Trial Step")

                run_trial_step(
                    components=components,
                    session=session,
                    photos_per_step_target=trial.frames_per_step_target,
                    step_strain_target=step_strain_target,
                    sample_height_mm=sample_height_mm,
                    encoder_sample_height_count=encoder_sample_height_count,
                    trial_id=trial_id,
                    trial_name=trial.name,
                    cam_settings_id=cam_settings_id,
                    postgres_db_dir='/share/CACHEDEV1_DATA/Public/postgres_data',
                    dest_machine_addr=server_ip,
                    dest_machine_user='domanlab',
                    is_calibration=False
                )

                step_strain_target += desired_strain_delta

                if step_strain_target > desired_strain_limit:
                    logging.info("Strain limit reached! Trial Complete")
                    break

        elif phantom:
            logging.info(f"Running Trial Step")
            camera_system_setup(components=components)
            run_trial_step(
                components=components,
                session=session,
                photos_per_step_target=trial.frames_per_step_target,
                step_strain_target=1,
                sample_height_mm=1,
                encoder_sample_height_count=1,
                trial_id=trial_id,
                trial_name=trial.name,
                cam_settings_id=cam_settings_id,
                postgres_db_dir='/share/CACHEDEV1_DATA/Public/postgres_data',
                dest_machine_addr=server_ip,
                dest_machine_user='domanlab',
                is_calibration=True
            )
            logging.info("Phantom Trial Complete.")
        
        else:
            logging.info(f"Trial {trial.id} has no associated sample")

        move_stepper_PID_target(
            stepper=components.get('big_stepper'),
            pi=components.get('big_stepper_PID'),
            enc=components.get('e5'),
            stepper_dc=85, 
            setpoint=5, 
            error=1
        )
        session.close()
    
    else:
        logging.info(f"Trial with ID: {trial_id} not found!")
    return


def num_photos_2_cam_stepper_freq(
        num_photos: int,
        seconds_per_photo: int = 1,
        steps_per_rotation: int = 54600,
):
    """
    num photos is photos desired per rotation
    need to estimate since cam is inconsistent
    :param num_photos:
    :param seconds_per_photo:
    :return:
    """

    freq = 1 / (num_photos * seconds_per_photo * (1 / steps_per_rotation))
    freq = freq / 3

    return round(freq, ndigits=0)


def decimate_frames(file_paths, desired_size):
    if len(file_paths) > desired_size:
        # Calculate the number of items to remove
        num_to_remove = len(file_paths) - desired_size
        # Randomly select file paths to remove
        files_to_remove = random.sample(file_paths, num_to_remove)
        
        for file_path in files_to_remove:
            try:
                # Attempt to delete the file
                os.remove(file_path)
                # Remove the file path from the list
                file_paths.remove(file_path)
                print(f"Removed: {file_path}")
            except OSError as e:
                print(f"Error deleting {file_path}: {e}")
    else:
        print("No need to reduce the list.")
    return file_paths


def run_trial_step(
        components,
        session,
        photos_per_step_target: int,
        step_strain_target: float,
        sample_height_mm: float,
        encoder_sample_height_count: int,
        trial_id: int,
        trial_name: str,
        cam_settings_id: int = 1,
        postgres_db_dir: str = '/share/CACHEDEV1_DATA/Public/postgres_data',
        dest_machine_addr: str = '192.168.1.2',
        dest_machine_user: str = 'domanlab',
        is_calibration: bool = False
        ):

    new_step = CompressionStep(
        name=uuid.uuid4(),
        strain_target=step_strain_target,
        compression_trial_id=trial_id
    )
    session.add(new_step)
    session.commit()
    new_step_id = new_step.id

    if not is_calibration:  # if not phantom trial then move crush stepper
        enc = components.get('e5')

        compression_dist_mm = sample_height_mm * step_strain_target
        compression_dist_encoder_counts = mm_to_counts(compression_dist_mm)
        stepper_setpoint = encoder_sample_height_count + compression_dist_encoder_counts

        move_stepper_PID_target(
            stepper=components.get('big_stepper'),
            pi=components.get('big_stepper_PID'),
            enc=components.get('e5'),
            stepper_dc=85, 
            setpoint=stepper_setpoint, 
            error=1
        )
        
        time.sleep(1)  # let force sensor cook

        new_sample_height_counts = abs(enc.read() - encoder_sample_height_count)
        new_sample_height_mm = counts_to_mm(new_sample_height_counts)
        actual_strain = new_sample_height_mm / sample_height_mm
        new_step.strain_encoder = actual_strain

        force = np.mean(sample_force_sensor(n_samples=100, components=components))
        new_step.force = force
        session.commit()
        print(f"Force @ Strain {actual_strain}: {force}")

    cam_settings = get_cam_settings(session=session, id=cam_settings_id)  # get cam settings from steps object!
    cam_ports = init_cameras(cam_settings=cam_settings)
    
    cam_steper_freq = num_photos_2_cam_stepper_freq(
        num_photos=photos_per_step_target
    )

    photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=cam_steper_freq)

    # decimate photo list to desired frames/sec

    # move files to db store
    current_directory = os.getcwd()
    absolute_filepaths_rpi = [filepath for name in photo_list for filepath in glob.glob(os.path.join(current_directory, f"{name}.*"))]
    absolute_filepaths_rpi = decimate_frames(file_paths=absolute_filepaths_rpi, desired_size=photos_per_step_target)
    
    trial_frames_dir = f'{postgres_db_dir}/{trial_name}'
    move_trial_assets(
        absolute_asset_filepaths=absolute_filepaths_rpi,
        dest_asset_dir=trial_frames_dir,
        dest_machine_user=dest_machine_user,
        dest_machine_addr=dest_machine_addr,
        interfaces=['eth0']
    )

    filenames = [os.path.basename(filepath) for filepath in absolute_filepaths_rpi]
    for filename in filenames:
        name = os.path.splitext(filename)[0]
        file_ext = os.path.splitext(filename)[1].strip(".")
        new_frame = Frame(
            name=name,
            file_extension=file_ext,
            file_name=filename,
            camera_setting_id=cam_settings_id,
            compression_step_id=new_step_id
        )
        session.add(new_frame)
    session.commit()
    return


if __name__ == '__main__':
    run_trial()