import logging
import threading
import time

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
from compression_testing_data.models.testing import CompressionTrial, CompressionStep

from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings, eosr50_continuous_capture_and_save    
from compression_tester_controls.sys_protocols import platon_setup, init_cameras, sys_init, home_camera_system, capture_step_frames, camera_system_setup
from compression_tester_controls.sys_functions import sample_force_sensor, get_a201_Rf, move_big_stepper_to_setpoint

from src.compression_tester_controller.file_management import transfer_files

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)


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

def run_trial(trial_id: int = 11):
    components = sys_init()

    # for testing
    encoder_zero_count = 7776
    encoder_sample_height_count = 4797

    # encoder_zero_count, encoder_sample_height_count = platon_setup(components=components)
    sample_height_counts = abs(encoder_zero_count - encoder_sample_height_count)
    sample_height_mm = counts_to_mm(sample_height_counts)
    
    logging.info(f"Sample Height: {sample_height_mm}")
    # pull sample from DB! can full from id in trial
    # pull trial from db
    # translate to mm
    # push to db

    force_zero = np.mean(sample_force_sensor(n_samples=100, components=components))
    print(f"Force @ Step: {force_zero}")
    # push force zero to trial in db

    camera_system_setup(components=components)
    # from trial we get
    # force limit
    # strain limit
    # strain delta
    strain_min = 0
    desired_strain_limit = 0.8
    desired_strain_delta = 0.1
    force_limit = 1000

    step_strain = strain_min
    while True:
        compression_dist_mm = sample_height_mm * step_strain
        compression_dist_encoder_counts = mm_to_counts(compression_dist_mm)
        stepper_setpoint = encoder_sample_height_count - compression_dist_encoder_counts
        
        # move platon - stop at max force - modify func to stop at max force
        # need to use threading to run force sensor and stepper move
        # move_big_stepper_to_setpoint(
            # components=components, 
            # setpoint=stepper_setpoint/, 
            # error=5
            # )

        print(step_strain)  # do the step using i as stran
        # move platon - stop at max force

        step_strain += desired_strain_delta

        if step_strain > desired_strain_limit:
            logging.info("Strain limit reached! Trial Complete")
            break

        # create steps - ensure first step is zero - limit to 2mm max compression
        # run steps one by one
        # move platon
        # check for force overload
        # get photos

        # run_trial_step(components=components)
    # move platon back to zero70007
    return

def run_trial_step(components):
    # ensure dir structure for frames? - do this in the transfer handler
    # move crusher to strain desired

    force = np.mean(sample_force_sensor(n_samples=100, components=components))
    print(f"Force @ Step: {force}")

    cam_settings = get_cam_settings(id=1)  # get cam settings from steps object!
    cam_ports = init_cameras(cam_settings=cam_settings)
    
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
        if time.time() - start > 5:
            stop_event.set()
            for thread in cam_threads:
                thread.join()
            break
    all_photos = [item for sublist in photos for item in sublist]
    
    import os
    dest_pass = os.environ.get('DOMANLAB_PASS')

    dest_dir = '/share/CACHEDEV1_DATA/Public/postgres_data/frames_temp/'
    transfer_files(
        file_list=all_photos,
        dest_machine_dir=dest_dir,
        dest_machine_user='daniel',
        dest_machine_addr='192.168.1.2',
        interfaces=['eth0'],
        dest_pass=dest_pass
    )


    # photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=500)
    # print(f"step Photos: {photo_list}")
    # move photos to server
    # enter photos in server db

    return


if __name__ == '__main__':
    run_trial_step(sys_init())