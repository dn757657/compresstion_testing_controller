import logging

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from sqlalchemy import select

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

def run_trial():
    components = sys_init()
    encoder_zero_count, encoder_sample_height_count = platon_setup(components=components)
    sample_height = abs(encoder_sample_height_count - encoder_zero_count)
    # translate to mm
    # push to db

    camera_system_setup(components=components)

    # create steps - ensure first step is zero - limit to 2mm max compression
    # run steps one by one
    # move platon
    # check for force overload

    # run_trial_step(components=components)
    return

# def run_trial_step(components):
#     # ensure dir structure for frames? - do this in the transfer handler
#     # move crusher to strain desired

#     # force = np.mean(sample_force_sensor(n_samples=100, components=components))
#     # print(f"Force @ Step: {force}")

#     cam_settings = get_cam_settings(id=1)  # get cam settings from steps object!
#     cam_ports = init_cameras(cam_settings=cam_settings)

#     # maybe add the base dir these are going to also
#     for i in range(0, 2):
#         force = sample_force_sensor(n_samples=100, components=components)
#         print(f"Force @ Step: {force}")
        
#         photo_list = capture_step_frames(cam_ports=cam_ports, components=components, stepper_freq=500)
#         print(f"step Photos: {photo_list}")
#     # take photo, push to db

#     # TODO need to complete sample, this can also be done post, since it involves volume:
#     #   - essentially if a strain step target is 0 then we can derive the sample height and diam
#     #   - add height after first scan?? or should this be in the steps or stl?

#     # get force zero - get n samples from adc channel obs and avg before moving motor
#     #   store in compression trial
#     # find encoder zero - do we store this somewhere
#     #   store on machine - add method to encoder class to reset encoder count at lower platon
#     # make steps
#     # run steps, run in order of descending strain
#     #   move motor
#     #       first step use special protocol to line up to sample
#     #   complete step, record strain, force, etc
#     #   transfer frames and make entries
#     #   check entries using base dir in dir structure
#     return


if __name__ == '__main__':
    run_trial()