import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from sqlalchemy import select
import numpy as np

from compression_testing_data.main import parse_gphoto_config_for_sql, parse_cam_config_dict_for_gphoto, parse_sql_gphoto_config_for_gphoto
from compression_testing_data.meta import Session
from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.acquisition_settings import CameraSetting
from compression_testing_data.models.testing import CompressionTrial, CompressionStep

from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings, eosr50_continuous_capture_and_save    
from compression_tester_controls.sys_protocols import platon_setup, init_cameras, sys_init, home_camera_system, capture_step_frames, camera_system_setup
from compression_tester_controls.sys_functions import sample_force_sensor


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


def encoder_to_mm(encoder_steps):
    mm = encoder_steps * (6/1000)
    return mm


def find_force_sensor_Rf():
    components = sys_init()
    a201 = components.get("A201")

    rf = a201.get_rf(rs=1000)
    print(f"{rf}")

    return

def run_trial(trial_id: int = 11):
    components = sys_init()
    encoder_zero_count, encoder_sample_height_count = platon_setup(components=components)
    sample_height_counts = abs(encoder_sample_height_count - encoder_zero_count)
    print(f"Sample Height: {encoder_to_mm(encoder_sample_height_count)}")
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

        print(i)  # do the step using i as stran
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
    return

def run_trial_step(components):
    # ensure dir structure for frames? - do this in the transfer handler
    # move crusher to strain desired

    force = np.mean(sample_force_sensor(n_samples=100, components=components))
    print(f"Force @ Step: {force}")

    cam_settings = get_cam_settings(id=1)  # get cam settings from steps object!
    cam_ports = init_cameras(cam_settings=cam_settings)
        
    photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=500)
    print(f"step Photos: {photo_list}")
    # move photos to server
    # enter photos in server db

    return


if __name__ == '__main__':
    # run_trial()
    find_force_sensor_Rf()