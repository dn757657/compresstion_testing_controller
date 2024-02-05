import logging
import uuid

from sqlalchemy import select

from compression_testing_data.main import parse_gphoto_config_for_sql, parse_cam_config_dict_for_gphoto
from compression_testing_data.meta import Session
from compression_testing_data.models.samples import Print, Sample
from compression_testing_data.models.testing import CompressionTrial, CompressionStep
from compression_tester_controls.components.canon_eosr50 import gphoto2_get_active_ports, gpohoto2_get_camera_settings    

def store_current_camera_settings():
    ports = gphoto2_get_active_ports()
    config = gpohoto2_get_camera_settings(port=ports[0])
    dict_config = parse_gphoto_config_for_sql(config_output=config)
    print(f"dict config: {dict_config}")
    gphoto_config = parse_cam_config_dict_for_gphoto(dict_config=dict_config)
    print(f"list (gphoto) config: {gphoto_config}")
    pass


def run_trial_steps():
   # fetch camera settings


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
    store_current_camera_settings()
