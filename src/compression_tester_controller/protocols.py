import logging
import uuid

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

from sqlalchemy import select

from compression_testing_data.main import parse_gphoto_config_for_sql, parse_cam_config_dict_for_gphoto, parse_sql_gphoto_config_for_gphoto
from compression_testing_data.meta import Session
from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.acquisition_settings import CameraSetting
from compression_testing_data.models.testing import CompressionTrial, CompressionStep
from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings    

def store_camera_settings(port = None):
    if not port:
        ports = gphoto2_get_active_ports()
        port = ports[0]

    config = gpohoto2_get_camera_settings(port=port)
    logging.info(f"Retrieving Settings from Camera @ {port}")

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


def run_trial_steps():
   # fetch camera settings & init camera


    # TODO need to complete sample, this can also be done post, since it involves volume:
    #   - essentially if a strain step target is 0 then we can derive the sample height and diam
    #   - add height after first scan?? or should this be in the steps or stl?

    # get force zero - get n samples from adc channel obs and avg before moving motor
    #   store in compression trial
    # find encoder zero - do we store this somewhere
    #   store on machine - add method to encoder class to reset encoder count at lower platon
    # make steps
    # run steps, run in order of descending strain
    #   move motor
    #       first step use special protocol to line up to sample
    #   complete step, record strain, force, etc
    #   transfer frames and make entries
    #   check entries using base dir in dir structure
    return


if __name__ == '__main__':
    get_cam_settings(id=2)
